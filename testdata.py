import os
import csv
import time
import sqlite3
import threading
from datetime import datetime
from flask import Flask, render_template, abort

app = Flask(__name__)

DB_FILE = 'carehouse.db'
CSV_FOLDER = 'incoming_csv'

if not os.path.exists(CSV_FOLDER):
    os.makedirs(CSV_FOLDER)

def parse_hardware_timestamp(raw_string):
    """
    Cleans and validates the incoming sensor time string.
    Since your sensor uses 'YYYY-MM-DD HH:MM:SS', we can pass it right through.
    """
    clean_string = raw_string.strip()
    try:
        # Validate that it matches your real format: YYYY-MM-DD HH:MM:SS
        datetime.strptime(clean_string, "%Y-%m-%d %H:%M:%S")
        return clean_string
    except Exception:
        # Fallback to current system time if a row is completely mangled
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def automated_csv_polling_worker():
    """Background loop that ingests real sensor logs into carehouse.db"""
    while True:
        try:
            active_csv_files = [f for f in os.listdir(CSV_FOLDER) if f.endswith('.csv')]
            if active_csv_files:
                connection = sqlite3.connect(DB_FILE)
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys = ON;")
                
                # Fetch reference ID for 403号室
                cursor.execute("SELECT room_id FROM rooms WHERE room_name = '403号室' LIMIT 1")
                room_record = cursor.fetchone()
                
                if room_record:
                    room_id = room_record[0]
                    
                    for filename in active_csv_files:
                        target_path = os.path.join(CSV_FOLDER, filename)
                        
                        with open(target_path, mode='r', encoding='utf-8') as active_file:
                            csv_reader = csv.reader(active_file)
                            for data_row in csv_reader:
                                # Safety skip: line must have at least 3 items to be valid
                                if not data_row or len(data_row) < 3:
                                    continue
                                    
                                # --- FIXED: Explicitly grab only the first 3 columns ---
                                # This prevents the unpacking error if there are extra commas at the end
                                raw_time = data_row[0]
                                temp = data_row[1]
                                hum = data_row[2]
                                
                                # Skip header row labels if present
                                if "datetime" in raw_time.lower() or "temperature" in temp.lower():
                                    continue
                                    
                                try:
                                    db_formatted_time = parse_hardware_timestamp(raw_time)
                                    
                                    cursor.execute('''
                                        INSERT INTO climate_readings (room_id, temperature, humidity, recorded_at)
                                        VALUES (?, ?, ?, ?)
                                    ''', (room_id, float(temp.strip()), float(hum.strip()), db_formatted_time))
                                except ValueError as num_err:
                                    print(f"Skipping unparseable data row values {data_row[:3]}: {num_err}")
                                    
                    connection.commit()
                connection.close()
                
                # Clear raw data out of queue folder after parsing successfully
                for filename in active_csv_files:
                    os.remove(os.path.join(CSV_FOLDER, filename))
                    print(f"Successfully processed and removed: {filename}")
                    
        except Exception as error:
            print(f"Error executing file integration thread: {error}")
            
        time.sleep(2)

# Start background file scanning thread
threading.Thread(target=automated_csv_polling_worker, daemon=True).start()

def compile_dashboard_telemetry(target_room_name):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    cursor.execute('''
        SELECT r.room_name, p.patient_name 
        FROM room_assignments ra
        JOIN rooms r ON ra.room_id = r.room_id
        JOIN patients p ON ra.patient_id = p.patient_id
        WHERE r.room_name = ? AND ra.is_active = 1
        LIMIT 1
    ''', (target_room_name,))
    meta_dataset = cursor.fetchone()
    
    if not meta_dataset:
        connection.close()
        return None
        
    room_title, resident_name = meta_dataset
    
    # Grab up to 50 latest telemetry points
    cursor.execute('''
        SELECT cr.temperature, cr.humidity, cr.recorded_at 
        FROM climate_readings cr
        JOIN rooms r ON cr.room_id = r.room_id
        WHERE r.room_name = ?
        ORDER BY cr.reading_id DESC LIMIT 50
    ''', (target_room_name,))
    reading_history = cursor.fetchall()
    connection.close()
    
    if not reading_history:
        return {
            "room_name": room_title,
            "patient_name": resident_name,
            "latest": {"temp": "--", "humidity": "--", "date": "データ待機中"},
            "history": {"temps": [], "humidities": [], "labels": []}
        }
        
    reading_history.reverse()
    
    return {
        "room_name": room_title,
        "patient_name": resident_name,
        "latest": {
            "temp": reading_history[-1][0], 
            "humidity": reading_history[-1][1], 
            "date": reading_history[-1][2]
        },
        "history": {
            "temps": [item[0] for item in reading_history],
            "humidities": [item[1] for item in reading_history],
            "labels": [item[2] for item in reading_history]
        }
    }

@app.route('/')
def route_home_portal():
    return render_template('home.html')

@app.route('/rooms')
def route_room_directory():
    return render_template('rooms.html')

@app.route('/room/<int:room_number>')
def route_room_detail(room_number):
    if room_number != 403:
        abort(404)
        
    formatted_room_name = f"{room_number}号室"
    data_payload = compile_dashboard_telemetry(formatted_room_name)
    
    if data_payload:
        return render_template(
            'room_detail.html', 
            room_name=data_payload["room_name"],
            patient_name=data_payload["patient_name"],
            latest=data_payload["latest"],
            history=data_payload["history"]
        )
    return "Database Error: Ensure init_db.py has been executed.", 500

if __name__ == '__main__':
    app.run(debug=True)
