import os
import time
import sqlite3
import csv

DB_FILE = 'carehouse.db'
CSV_FOLDER = 'incoming_csv'

def process_headerless_telemetry_csv(file_path, filename):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Target Room 403 explicitly per Option A
        target_room_name = "403号室"
        cursor.execute("SELECT room_id FROM rooms WHERE room_name = ? LIMIT 1", (target_room_name,))
        room_row = cursor.fetchone()
        
        if not room_row:
            print(f"Database Error: '{target_room_name}' does not exist in the rooms table.")
            return False
        room_id = room_row[0]
        
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            if filename == 'temp_hum.csv':
                for row in reader:
                    if not row or len(row) < 3:
                        continue
                    
                    # Safety Check: Skip the header row if the text headers exist
                    if row[0].strip().lower() == 'timestamp' or 'temp' in row[1].lower():
                        continue
                        
                    timestamp = row[0].strip()   # '2026-06-05 15:50:11'
                    temperature = float(row[1])  # 26.8
                    humidity = float(row[2])     # 54.6
                    
                    # FIXED: Matched table 'room_live_buffer' and filled missing bpm value as 0 (or a default baseline)
                    cursor.execute('''
                        INSERT INTO room_live_buffer (room_id, bpm, temp, humidity, timestamp)
                        VALUES (?, 0, ?, ?, ?)
                    ''', (room_id, temperature, humidity, timestamp))
                        
            elif filename == 'heart_rate.csv':
                for row in reader:
                    if not row or len(row) < 2:
                        continue
                    
                    # Safety Check: Skip the header row if the text headers exist
                    if row[0].strip().lower() == 'timestamp' or 'bpm' in row[1].lower() or 'heart' in row[1].lower():
                        continue
                        
                    timestamp = row[0].strip()   # '2026-06-05 15:49:29'
                    bpm = int(row[1])            # 115
                    
                    # FIXED: Matched table 'room_live_buffer' and filled missing temp/humidity values as 0.0
                    cursor.execute('''
                        INSERT INTO room_live_buffer (room_id, bpm, temp, humidity, timestamp)
                        VALUES (?, ?, 0.0, 0.0, ?)
                    ''', (room_id, bpm, timestamp))
                        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error parsing raw data spreadsheet {filename}: {e}")
        return False
    finally:
        conn.close()

def automated_csv_polling_worker():
    print("Background CSV Polling thread active [Targeting: Raw 403 Log Files]...")
    while True:
        if os.path.exists(CSV_FOLDER):
            for target_file in ['temp_hum.csv', 'heart_rate.csv']:
                full_path = os.path.join(CSV_FOLDER, target_file)
                
                if os.path.exists(full_path):
                    success = process_headerless_telemetry_csv(full_path, target_file)
                    if success:
                        try:
                            os.remove(full_path)
                            print(f"Successfully digested and cleared raw telemetry: {target_file}")
                        except Exception as e:
                            print(f"File system lock cleanup conflict for {target_file}: {e}")
                            
        time.sleep(3)