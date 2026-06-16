import os
import sqlite3
from datetime import datetime, timedelta
import flask_bcrypt

DB_FILE = 'carehouse.db'

def setup_version_1_3_communication_database():
    print("--- Starting Version 1.3 Communication Database Upgrade ---")
    
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print("Cleared old database file.")
        except PermissionError:
            print("CRITICAL: carehouse.db is locked. Stop your Flask server first!")
            return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Core Directories & Assignments Tables
    cursor.execute('''
        CREATE TABLE patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            age INTEGER,
            height REAL,
            weight REAL,
            created_at TEXT NOT NULL
        )
    ''')
    cursor.execute('CREATE TABLE rooms (room_id INTEGER PRIMARY KEY AUTOINCREMENT, room_name TEXT NOT NULL UNIQUE)')
    cursor.execute('''
        CREATE TABLE room_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
    ''')
    
    # 2. UPGRADED: Telemetry Buffers & Historical Ledgers
    # Table A: Short-term 1-minute averages (Maintains up to 60 rows max per room)
    cursor.execute('''
        CREATE TABLE room_live_buffer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            bpm INTEGER NOT NULL,
            temp REAL NOT NULL,
            humidity REAL NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')
    
    # Table B: Long-term 1-hour historical averages (Maintains 24 entries a day per room)
    cursor.execute('''
        CREATE TABLE room_historical_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            avg_bpm INTEGER NOT NULL,
            avg_temp REAL NOT NULL,
            avg_humidity REAL NOT NULL,
            log_hour TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    ''')

    # 3. Mail System Tables (Custom Questionnaires + One-time Replies)
    cursor.execute('''
        CREATE TABLE patient_mails (
            mail_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            target_patient_id INTEGER NOT NULL,
            response_type TEXT NOT NULL, -- 'text' or 'choices'
            choice_options TEXT,         -- Comma-separated options: 'はい,いいえ'
            created_at TEXT NOT NULL,
            FOREIGN KEY (target_patient_id) REFERENCES patients(patient_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE mail_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mail_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            submitted_answer TEXT NOT NULL,
            replied_at TEXT NOT NULL,
            FOREIGN KEY (mail_id) REFERENCES patient_mails(mail_id),
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
            UNIQUE(mail_id, patient_id) -- Locks down one-time reply rule
        )
    ''')

    # 4. Notice System Tables (Read-Only Bulletins + Tracking Views)
    cursor.execute('''
        CREATE TABLE system_notices (
            notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            recipient_type TEXT NOT NULL, -- 'all' or 'individual'
            target_patient_id INTEGER,    -- NULL if sent to building broadcast
            created_at TEXT NOT NULL,
            FOREIGN KEY (target_patient_id) REFERENCES patients(patient_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE notice_views (
            view_id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            viewed_at TEXT NOT NULL,
            FOREIGN KEY (notice_id) REFERENCES system_notices(notice_id),
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
            UNIQUE(notice_id, patient_id)
        )
    ''')

    # 5. Security Accounts
    cursor.execute('''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            patient_id INTEGER,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
    ''')
    
    # --- SEEDING BASE DATA ---
    for r_num in range(401, 410):
        cursor.execute("INSERT INTO rooms (room_name) VALUES (?)", (f"{r_num}号室",))
        
    cursor.execute("SELECT room_id FROM rooms WHERE room_name = '403号室' LIMIT 1")
    room_403_id = cursor.fetchone()[0]
    
    current_time = datetime.now()
    now_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Generate an explicit hour anchor point for seeding historical logs
    top_of_hour_str = current_time.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("INSERT INTO patients (patient_name, age, height, weight, created_at) VALUES ('マルマル', 78, 162.5, 58.0, ?)", (now_str,))
    maru_id = cursor.lastrowid
    cursor.execute("INSERT INTO room_assignments (room_id, patient_id, assigned_at, is_active) VALUES (?, ?, '2026-05-29', 1)", (room_403_id, maru_id))
    
    hasher = flask_bcrypt.Bcrypt()
    cursor.execute("INSERT INTO users (username, password_hash, role, patient_id) VALUES ('admin', ?, 'staff', NULL)", (hasher.generate_password_hash('admin1234').decode('utf-8'),))
    cursor.execute("INSERT INTO users (username, password_hash, role, patient_id) VALUES ('maru', ?, 'patient', ?)", (hasher.generate_password_hash('maru1234').decode('utf-8'), maru_id))
    
    # Seeding initial rolling baseline states to prevent empty query loops on cold boot
    cursor.execute('''
        INSERT INTO room_live_buffer (room_id, bpm, temp, humidity, timestamp) 
        VALUES (?, 72, 24.5, 50.0, ?)
    ''', (room_403_id, now_str))
    
    cursor.execute('''
        INSERT INTO room_historical_log (room_id, avg_bpm, avg_temp, avg_humidity, log_hour) 
        VALUES (?, 72, 24.5, 50.0, ?)
    ''', (room_403_id, top_of_hour_str))
    
    # Seed 1 Sample Broadcast Notice (Unread by default)
    cursor.execute('''
        INSERT INTO system_notices (title, body, recipient_type, target_patient_id, created_at)
        VALUES ('施設内ワックス掛けのお知らせ', '明日10:00より廊下のワックス清掃を行います。足元にご注意ください。', 'all', NULL, ?)
    ''', (now_str,))
    
    # Seed 1 Sample Customizable Mail Survey (Unreplied by default)
    cursor.execute('''
        INSERT INTO patient_mails (title, body, target_patient_id, response_type, choice_options, created_at)
        VALUES ('季節のイベント参加確認', '来週月曜日に七夕祭りを開催します。会場にお越しになりますか？', ?, 'choices', '参加する,部屋で過ごす', ?)
    ''', (maru_id, now_str))
    
    conn.commit()
    conn.close()
    print("--- Database Version 1.3 Created Successfully ---")

if __name__ == '__main__':
    setup_version_1_3_communication_database()