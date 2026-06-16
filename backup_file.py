import os
import sqlite3
import threading
import datetime
import random  # Maintained for background scheduling or simulated failover streams
import time
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_bcrypt import Bcrypt

from sensor_manager import automated_csv_polling_worker, DB_FILE, CSV_FOLDER
from auth_manager import login_required, verify_user_credentials
from testdata import compile_dashboard_telemetry

app = Flask(__name__)
app.secret_key = 'carehouse_secret_signing_token_v1.3_core'
bcrypt = Bcrypt(app)

if not os.path.exists(CSV_FOLDER):
    os.makedirs(CSV_FOLDER)

# -------------------------------------------------------------------------
# DUAL-STREAM IN-MEMORY STATE CORE STORAGE
# -------------------------------------------------------------------------
# Global cache for instant real-time UI rendering without database locking
REALTIME_ROOM_DATA = {}

# Active memory collection arrays for processing 10-second packets
raw_memory_buffers = {}

# Persistent tracking states for clock transitions
last_processed_minute = -1
last_processed_hour = -1

# Start background file polling worker thread to parse dropped telemetry CSVs automatically
threading.Thread(target=automated_csv_polling_worker, daemon=True).start()

# -------------------------------------------------------------------------
# BACKGROUND TIME-MATCHING PIPELINE ENGINE
# -------------------------------------------------------------------------
def run_iot_data_pipeline_engine():
    """
    Monitors global time states continuously. Aggregates data blocks in RAM,
    filters null frames, and flushes averages to the database on clock transitions.
    """
    global last_processed_minute, last_processed_hour
    print("--- CareHouse IoT Data Processing Pipeline Engine Active ---")
    
    while True:
        try:
            # Connect safely to read room states dynamically
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT room_id, room_name FROM rooms")
            all_rooms = cursor.fetchall()
            conn.close()
            
            # Simulated data stream fallback or hardware queue reader loop
            for room_row in all_rooms:
                r_id = room_row["room_id"]
                r_name = room_row["room_name"]
                
                # Extracting raw string prefix identifier (e.g., "403号室" -> "403")
                clean_room_key = r_name.replace("号室", "")
                
                # SIMULATED PACKET INPUT: Replace with an MQTT or CSV stream lookup if necessary
                simulated_packet = {
                    "room_id": r_id,
                    "room_number": clean_room_key,
                    "bpm": random.randint(65, 95) if random.random() > 0.05 else None,  # 5% Misfire validation check
                    "temp": round(random.uniform(21.0, 26.5), 1),
                    "humidity": round(random.uniform(40.0, 65.0), 1)
                }
                
                # --- PHASE 1: STRICTOR VALIDATION FILTER ---
                bpm = simulated_packet.get("bpm")
                temp = simulated_packet.get("temp")
                humidity = simulated_packet.get("humidity")
                
                if bpm is None or temp is None or humidity is None:
                    # Drop frame instantly without processing calculations
                    continue
                
                # Fetch active resident name map context details safely
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.patient_name, p.age FROM room_assignments ra
                    JOIN patients p ON ra.patient_id = p.patient_id
                    WHERE ra.room_id = ? AND ra.is_active = 1 LIMIT 1
                ''', (r_id,))
                p_res = cursor.fetchone()
                conn.close()
                
                p_name = p_res[0] if p_res else "入居者未登録"
                p_age = p_res[1] if p_res else 0
                
                # --- PHASE 2: INSTANT REAL-TIME DISPLAY STREAM ---
                REALTIME_ROOM_DATA[clean_room_key] = {
                    "name": p_name,
                    "age": p_age,
                    "bpm": bpm,
                    "temp": temp,
                    "humidity": humidity,
                    "date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # --- PHASE 3: ACCUMULATE IN MEMORY BUFFER ---
                if r_id not in raw_memory_buffers:
                    raw_memory_buffers[r_id] = []
                    
                raw_memory_buffers[r_id].append({
                    "bpm": bpm,
                    "temp": temp,
                    "humidity": humidity
                })
            
            # --- PHASE 4: CLOCK-MATCHING TRANSITIONS ---
            now = datetime.datetime.now()
            current_minute = now.minute
            current_hour = now.hour
            
            if last_processed_minute == -1:
                last_processed_minute = current_minute
                last_processed_hour = current_hour
                
            # Minute boundary reached -> Flush 1-Minute Averages to live buffer table
            if current_minute != last_processed_minute:
                flush_minute_averages()
                last_processed_minute = current_minute
                
            # Hour boundary reached -> Flush 1-Hour Aggregations to long-term history ledger
            if current_hour != last_processed_hour:
                flush_hourly_averages(now)
                last_processed_hour = current_hour
                
        except Exception as e:
            print(f"Pipeline Engine Runtime Intercept: {e}")
            
        time.sleep(10)  # Regular 10-second system cycle check

def flush_minute_averages():
    """Reduces high-frequency frames to a single 1-minute averaged entry and truncates old entries."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for room_id, frames in list(raw_memory_buffers.items()):
        if not frames:
            continue
            
        avg_bpm = int(sum(f["bpm"] for f in frames) / len(frames))
        avg_temp = round(sum(f["temp"] for f in frames) / len(frames), 1)
        avg_humidity = round(sum(f["humidity"] for f in frames) / len(frames), 1)
        
        cursor.execute('''
            INSERT INTO room_live_buffer (room_id, bpm, temp, humidity, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (room_id, avg_bpm, avg_temp, avg_humidity, now_str))
        
        # Self-Cleaning: Keep the database file size small by deleting entries older than 1 hour
        cursor.execute('''
            DELETE FROM room_live_buffer WHERE timestamp < datetime('now', '-1 hour')
        ''')
        
        # Clear RAM buffer for the next 1-minute cycle
        raw_memory_buffers[room_id] = []
        
    conn.commit()
    conn.close()

def flush_hourly_averages(current_time):
    """Calculates historical logs by aggregating the 1-minute data points into an hourly baseline entry."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    top_of_hour_str = current_time.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("SELECT DISTINCT room_id FROM room_live_buffer")
    active_room_ids = [row[0] for row in cursor.fetchall()]
    
    for room_id in active_room_ids:
        cursor.execute('''
            SELECT AVG(bpm), AVG(temp), AVG(humidity) FROM room_live_buffer
            WHERE room_id = ?
        ''', (room_id,))
        aggregated_res = cursor.fetchone()
        
        if aggregated_res and aggregated_res[0] is not None:
            cursor.execute('''
                INSERT INTO room_historical_log (room_id, avg_bpm, avg_temp, avg_humidity, log_hour)
                VALUES (?, ?, ?, ?, ?)
            ''', (room_id, int(aggregated_res[0]), round(aggregated_res[1], 1), round(aggregated_res[2], 1), top_of_hour_str))
            
    conn.commit()
    conn.close()

# Start the optimized IoT tracking thread worker automatically on startup
threading.Thread(target=run_iot_data_pipeline_engine, daemon=True).start()


# --- INTERNAL SYSTEM HELPERS ---

def get_vacant_rooms():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT room_id, room_name FROM rooms 
        WHERE room_id NOT IN (SELECT room_id FROM room_assignments WHERE is_active = 1)
    ''')
    vacant = cursor.fetchall()
    conn.close()
    return vacant

def get_patient_badge_counts(patient_id):
    if not patient_id:
        return {"unread_notices": 0, "unreplied_mails": 0}
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Unread Notices count
    cursor.execute('''
        SELECT COUNT(*) FROM system_notices 
        WHERE (recipient_type = 'all' OR (recipient_type = 'individual' AND target_patient_id = ?))
        AND notice_id NOT IN (SELECT notice_id FROM notice_views WHERE patient_id = ?)
    ''', (patient_id, patient_id))
    unread_notices = cursor.fetchone()[0]
    
    # Unreplied Mails count
    cursor.execute('''
        SELECT COUNT(*) FROM patient_mails 
        WHERE target_patient_id = ?
        AND mail_id NOT IN (SELECT mail_id FROM mail_replies WHERE patient_id = ?)
    ''', (patient_id, patient_id))
    unreplied_mails = cursor.fetchone()[0]
    
    conn.close()
    return {"unread_notices": unread_notices, "unreplied_mails": unreplied_mails}

def fetch_latest_live_telemetry(room_name):
    """Upgraded: Pulls real-time states instantly from memory, eliminating slow database loops."""
    clean_key = room_name.replace("号室", "")
    if clean_key in REALTIME_ROOM_DATA:
        cached = REALTIME_ROOM_DATA[clean_key]
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.patient_id FROM room_assignments ra
            JOIN rooms r ON ra.room_id = r.room_id
            JOIN patients p ON ra.patient_id = p.patient_id
            WHERE r.room_name = ? AND ra.is_active = 1 LIMIT 1
        ''', (room_name,))
        p_row = cursor.fetchone()
        conn.close()
        
        p_id = p_row[0] if p_row else None
        return {"id": p_id, "name": cached["name"], "age": cached["age"], "temp": cached["temp"], "humidity": cached["humidity"], "bpm": cached["bpm"]}
        
    # Cold Boot Database Fallback Read Routine
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.patient_id, p.patient_name, p.age, r.room_id FROM room_assignments ra
        JOIN rooms r ON ra.room_id = r.room_id
        JOIN patients p ON ra.patient_id = p.patient_id
        WHERE r.room_name = ? AND ra.is_active = 1 LIMIT 1
    ''', (room_name,))
    patient_res = cursor.fetchone()
    if not patient_res:
        conn.close()
        return None
        
    p_id, p_name, p_age, r_id = patient_res
    
    cursor.execute('SELECT temp, humidity FROM room_live_buffer WHERE room_id = ? ORDER BY id DESC LIMIT 1', (r_id,))
    c_res = cursor.fetchone()
    cursor.execute('SELECT bpm FROM room_live_buffer WHERE room_id = ? ORDER BY id DESC LIMIT 1', (r_id,))
    v_res = cursor.fetchone()
    conn.close()
    
    return {
        "id": p_id, "name": p_name, "age": p_age,
        "temp": c_res[0] if c_res else "--",
        "humidity": c_res[1] if c_res else "--",
        "bpm": v_res[0] if v_res else "--"
    }


# ==========================================
#         PORTAL & SECURITY ROUTES
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def route_login_portal():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        prof = verify_user_credentials(u, p, bcrypt)
        if prof:
            session['user_id'] = prof['user_id']
            session['username'] = prof['username']
            session['role'] = prof['role']
            session['patient_id'] = prof['patient_id']
            return redirect(url_for('route_admin_dashboard') if prof['role'] == 'staff' else url_for('route_room_detail', room_number=403))
    return render_template('login.html')

@app.route('/logout')
def route_logout_action():
    session.clear()
    return redirect(url_for('route_login_portal'))

@app.route('/admin/dashboard')
@login_required(role_target='staff')
def route_admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/rooms')
@login_required(role_target='staff')
def route_room_directory():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT r.room_name, (SELECT COUNT(*) FROM room_assignments ra WHERE ra.room_id = r.room_id AND ra.is_active = 1) FROM rooms r')
    room_data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return render_template('rooms.html', room_data=room_data)


# ==========================================
#     MONITORING INTERFACES (PAGES 1 & 2)
# ==========================================

@app.route('/room/<int:room_number>')
@login_required()
def route_room_detail(room_number):
    if room_number != 403:
        abort(404)
        
    formatted_room_name = f"{room_number}号室"
    clean_key = str(room_number)
    
    # 1. Direct Realtime Fast Read Engine
    if clean_key in REALTIME_ROOM_DATA:
        cached_stream = REALTIME_ROOM_DATA[clean_key]
        data_payload = {
            "patient_id": session.get('patient_id'),
            "name": cached_stream["name"],
            "age": cached_stream["age"],
            "bpm": cached_stream["bpm"],
            "temp": cached_stream["temp"],
            "humidity": cached_stream["humidity"],
            "date": cached_stream["date"]
        }
    else:
        # Static Fallback Read configuration for system cold boot states
        data_payload = {
            "patient_id": session.get('patient_id'),
            "name": "マルマル",
            "age": 78,
            "bpm": "--",
            "temp": "--",
            "humidity": "--",
            "date": "データ待機中"
        }
        
    # 2. Extract historical arrays from the clean 1-minute buffer table
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT room_id FROM rooms WHERE room_name = ? LIMIT 1", (formatted_room_name,))
    r_row = cursor.fetchone()
    
    history_payload = {"temps": [], "humidities": [], "labels": []}
    p_id = None
    
    if r_row:
        room_id = r_row[0]
        # FIXED: Added the explicit JOIN statement to tie 'ra' and 'p' together cleanly
        cursor.execute('''
            SELECT p.patient_id FROM room_assignments ra 
            JOIN patients p ON ra.patient_id = p.patient_id
            WHERE ra.room_id = ? AND ra.is_active = 1 LIMIT 1
        ''', (room_id,))
        p_row = cursor.fetchone()
        p_id = p_row[0] if p_row else None
        
        cursor.execute('''
            SELECT temp, humidity, timestamp FROM room_live_buffer 
            WHERE room_id = ? ORDER BY id DESC LIMIT 50
        ''', (room_id,))
        buffer_history = cursor.fetchall()[::-1]
        
        history_payload = {
            "temps": [h[0] for h in buffer_history],
            "humidities": [h[1] for h in buffer_history],
            "labels": [h[2] for h in buffer_history]
        }
    conn.close()
    
    if p_id:
        data_payload["patient_id"] = p_id
        
    badge_payload = get_patient_badge_counts(data_payload["patient_id"])
    
    if session.get('role') == 'staff':
        return render_template('admin_room_view.html', room_number=room_number, data=data_payload)
    else:
        return render_template(
            'room_detail.html',
            room_number=room_number,
            room_name=formatted_room_name,
            patient_name=data_payload["name"],
            latest={
                "temp": data_payload["temp"],
                "humidity": data_payload["humidity"],
                "date": data_payload["date"]
            },
            data=data_payload,
            history=history_payload,
            badges=badge_payload
        )

@app.route('/room/<int:room_number>/history')
@login_required()
def route_room_history(room_number):
    if session.get('role') == 'patient' and room_number != 403:
        abort(403)
        
    f_room_name = f"{room_number}号室"
    
    # Get the time range selection from the URL query parameter (Default to '1h')
    time_range = request.args.get('range', '1h')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Fetch patient name and room ID mapping context
    cursor.execute('''
        SELECT p.patient_name, ra.room_id FROM room_assignments ra
        JOIN rooms r ON ra.room_id = r.room_id
        JOIN patients p ON ra.patient_id = p.patient_id
        WHERE r.room_name = ? AND ra.is_active = 1 LIMIT 1
    ''', (f_room_name,))
    p_row = cursor.fetchone()
    p_name = p_row[0] if p_row else "入居者未登録"
    room_id = p_row[1] if p_row else None
    
    dates, temps, humidities, bpms = [], [], [], []
    
    if room_id:
        if time_range == '24h':
            # --- 24-HOUR VIEW: Query the hourly aggregated historical log table ---
            cursor.execute('''
                SELECT avg_temp, avg_humidity, avg_bpm, log_hour FROM room_historical_log
                WHERE room_id = ? ORDER BY log_hour DESC LIMIT 24
            ''', (room_id,))
            historical_records = cursor.fetchall()[::-1]
            
            dates = [r[3] for r in historical_records]
            temps = [r[0] for r in historical_records]
            humidities = [r[1] for r in historical_records]
            bpms = [r[2] for r in historical_records]
        else:
            # --- 1-HOUR VIEW (DEFAULT): Query the high-resolution 1-minute buffer table ---
            cursor.execute('''
                SELECT temp, humidity, bpm, timestamp FROM room_live_buffer
                WHERE room_id = ? ORDER BY id DESC LIMIT 60
            ''', (room_id,))
            buffer_records = cursor.fetchall()[::-1]
            
            # Format timestamps to show just MM:SS or HH:MM for clarity in short term charts
            dates = [r[3] for r in buffer_records]
            temps = [r[0] for r in buffer_records]
            humidities = [r[1] for r in buffer_records]
            bpms = [r[2] for r in buffer_records]
        
    conn.close()
    
    history_payload = {
        "dates": dates, 
        "temps": temps, 
        "humidities": humidities,
        "bpm_dates": dates, 
        "bpms": bpms,
        "current_range": time_range  # Sent to frontend to highlight the active button
    }
    
    return render_template(
        'room_history.html', 
        room_number=room_number, 
        patient_name=p_name, 
        history=history_payload
    )


# ==========================================
#         PATIENT-SIDE INBOX HUB SYSTEM
# ==========================================

@app.route('/patient/notices')
@login_required()
def route_patient_notices():
    p_id = session.get('patient_id')
    if not p_id: abort(403)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT notice_id, title, body, created_at FROM system_notices
        WHERE recipient_type = 'all' OR target_patient_id = ?
        ORDER BY notice_id DESC
    ''', (p_id,))
    notices = cursor.fetchall()
    
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for row in notices:
        cursor.execute('INSERT OR IGNORE INTO notice_views (notice_id, patient_id, viewed_at) VALUES (?, ?, ?)', (row[0], p_id, now_str))
    
    conn.commit()
    conn.close()
    return render_template('patient_notices.html', notices=notices)

@app.route('/patient/mails', methods=['GET', 'POST'])
@login_required()
def route_patient_mails():
    p_id = session.get('patient_id')
    if not p_id: abort(403)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        mail_id = request.form.get('mail_id')
        answer = request.form.get('answer')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            cursor.execute('''
                INSERT INTO mail_replies (mail_id, patient_id, submitted_answer, replied_at)
                VALUES (?, ?, ?, ?)
            ''', (int(mail_id), p_id, answer, now_str))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
            
        return redirect(url_for('route_patient_mails'))
        
    cursor.execute('''
        SELECT m.mail_id, m.title, m.body, m.response_type, m.choice_options, m.created_at, r.submitted_answer
    FROM patient_mails m
        LEFT JOIN mail_replies r ON m.mail_id = r.mail_id AND r.patient_id = ?
        WHERE m.target_patient_id = ? ORDER BY m.mail_id DESC
    ''', (p_id, p_id))
    mails = cursor.fetchall()
    conn.close()
    return render_template('patient_mails.html', mails=mails)


# ==========================================
#     PATIENT-SIDE AI COMPANION INTERFACE
# ==========================================

@app.route('/patient/ai-assistant')
@login_required()
def route_patient_ai():
    p_id = session.get('patient_id')
    if not p_id: abort(403)
    
    p_name = session.get('username', '入居者')
    return render_template('patient_ai.html', patient_name=p_name)


# ==========================================
#     ADMIN COMMUNICATION DISPATCH
# ==========================================

@app.route('/admin/communication', methods=['GET', 'POST'])
@login_required(role_target='staff')
def route_admin_communication():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        title = request.form.get('title')
        body = request.form.get('body')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        selected_patient_ids = request.form.getlist('selected_patients')
        
        if not selected_patient_ids:
            flash("エラー：宛先が1人も選択されていません。", "error")
            conn.close()
            return redirect(url_for('route_admin_communication'))

        if form_type == 'notice':
            for p_id in selected_patient_ids:
                cursor.execute('''
                    INSERT INTO system_notices (title, body, recipient_type, target_patient_id, created_at) 
                    VALUES (?, ?, "individual", ?, ?)
                ''', (title, body, int(p_id), now_str))
            flash("お便り・通知が正常に発信されました。", "success")
                
        elif form_type == 'mail':
            resp_type = request.form.get('response_type')
            choices = request.form.get('choice_options') if resp_type == 'choices' else None
            
            for p_id in selected_patient_ids:
                cursor.execute('''
                    INSERT INTO patient_mails (title, body, target_patient_id, response_type, choice_options, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (title, body, int(p_id), resp_type, choices, now_str))
            flash("カスタムアンケートメールが正常に発信されました。", "success")
            
        conn.commit()
        return redirect(url_for('route_admin_communication'))
        
    cursor.execute('SELECT patient_id, patient_name FROM patients')
    all_patients = cursor.fetchall()
    
    cursor.execute('''
        SELECT n.notice_id, n.title, p.patient_name, n.created_at 
        FROM system_notices n
        LEFT JOIN patients p ON n.target_patient_id = p.patient_id
        ORDER BY n.notice_id DESC
    ''')
    notice_logs = cursor.fetchall()
    
    cursor.execute('''
        SELECT m.mail_id, m.title, p.patient_name, m.created_at, r.submitted_answer 
        FROM patient_mails m
        JOIN patients p ON m.target_patient_id = p.patient_id
        LEFT JOIN mail_replies r ON m.mail_id = r.mail_id AND r.patient_id = p.patient_id
        ORDER BY m.mail_id DESC
    ''')
    mail_logs = cursor.fetchall()
    
    conn.close()
    return render_template('admin_communication.html', patients=all_patients, notices=notice_logs, mails=mail_logs)


# ==========================================
#     ADMIN MANAGEMENT CRUD ROUTINES
# ==========================================

@app.route('/admin/patients', methods=['GET', 'POST'])
@login_required(role_target='staff')
def route_manage_patients():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        p_name = request.form.get('patient_name')
        p_age = request.form.get('age')
        p_height = request.form.get('height')
        p_weight = request.form.get('weight')
        r_id = request.form.get('room_id')
        manual_assigned_date = request.form.get('assigned_date') 
        system_log_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('INSERT INTO patients (patient_name, age, height, weight, created_at) VALUES (?, ?, ?, ?, ?)', (p_name, int(p_age), float(p_height), float(p_weight), system_log_time))
        new_p_id = cursor.lastrowid
        
        if r_id:
            cursor.execute('INSERT INTO room_assignments (room_id, patient_id, assigned_at, is_active) VALUES (?, ?, ?, 1)', (int(r_id), new_p_id, manual_assigned_date))
        conn.commit()
        return redirect(url_for('route_manage_patients'))
        
    cursor.execute('SELECT p.patient_id, p.patient_name, p.age, p.height, p.weight, ra.assigned_at, r.room_name FROM patients p LEFT JOIN room_assignments ra ON p.patient_id = ra.patient_id AND ra.is_active = 1 LEFT JOIN rooms r ON ra.room_id = r.room_id')
    roster = cursor.fetchall()
    conn.close()
    return render_template('manage_patients.html', roster=roster, vacant_rooms=get_vacant_rooms())

@app.route('/admin/patients/discharge/<int:patient_id>')
@login_required(role_target='staff')
def route_discharge_patient(patient_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE room_assignments SET is_active = 0 WHERE patient_id = ? AND is_active = 1', (patient_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('route_manage_patients'))

if __name__ == '__main__':
    app.run(debug=True)