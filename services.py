import sqlite3
import datetime
import random
import time
from sensor_manager import DB_FILE

class TelemetryCacheManager:
    """
    OOP Core Service managing the high-speed, in-memory real-time room data storage.
    By housing the global dictionary here, we protect the live state cache and 
    allow any decoupled route blueprint to instantly fetch tracking packets without conflicts.
    """
    def __init__(self):
        # This replaces the loose global REALTIME_ROOM_DATA = {} dictionary
        self._realtime_room_data = {}

    def update_room(self, room_key, payload):
        """Thread-safe update of a room's active telemetry parameters."""
        self._realtime_room_data[str(room_key)] = payload

    def get_room(self, room_key):
        """Instant extraction of a room state. Returns None if the channel hasn't received data."""
        return self._realtime_room_data.get(str(room_key))

    def has_room(self, room_key):
        """Verifies if the cache currently holds packets for a target room."""
        return str(room_key) in self._realtime_room_data


class CareHouseDatabaseService:
    """
    Encapsulates internal relational database utility tasks.
    Extracts loose SQL utility helper blocks completely out of route layers.
    """
    @staticmethod
    def get_vacant_rooms():
        """Queries the database to return all room entities without an active assignment."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT room_id, room_name FROM rooms 
            WHERE room_id NOT IN (SELECT room_id FROM room_assignments WHERE is_active = 1)
        ''')
        vacant = cursor.fetchall()
        conn.close()
        return vacant

    @staticmethod
    def get_patient_badge_counts(patient_id):
        """Calculates dynamic real-time communication badges (unread notices and mail) for a resident."""
        if not patient_id:
            return {"unread_notices": 0, "unreplied_mails": 0}
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Unread Notices count query
        cursor.execute('''
            SELECT COUNT(*) FROM system_notices 
            WHERE (recipient_type = 'all' OR (recipient_type = 'individual' AND target_patient_id = ?))
            AND notice_id NOT IN (SELECT notice_id FROM notice_views WHERE patient_id = ?)
        ''', (patient_id, patient_id))
        unread_notices = cursor.fetchone()[0]
        
        # Unreplied Mails count query
        cursor.execute('''
            SELECT COUNT(*) FROM patient_mails 
            WHERE target_patient_id = ?
            AND mail_id NOT IN (SELECT mail_id FROM mail_replies WHERE patient_id = ?)
        ''', (patient_id, patient_id))
        unreplied_mails = cursor.fetchone()[0]
        
        conn.close()
        return {"unread_notices": unread_notices, "unreplied_mails": unreplied_mails}


class IoTDataPipelineEngine:
    """
    The background time-matching orchestration processing engine.
    Monitors high-frequency frames in RAM buffers, screens out corruption anomalies, 
    and handles structured aggregations down to the relational tables on time boundaries.
    """
    def __init__(self, telemetry_cache: TelemetryCacheManager):
        self.cache = telemetry_cache
        self.raw_memory_buffers = {}
        self.last_processed_minute = -1
        self.last_processed_hour = -1

    def run_engine_loop(self):
        """Continuous pipeline loop. Designed to run inside an asynchronous daemon thread."""
        print("--- CareHouse IoT Data Processing Pipeline Engine Active (OOP-Refactored) ---")
        while True:
            try:
                # Connect safely to read room states dynamically
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT room_id, room_name FROM rooms")
                all_rooms = cursor.fetchall()
                conn.close()
                
                # Process simulated sensor data stream
                for room_row in all_rooms:
                    r_id = room_row["room_id"]
                    r_name = room_row["room_name"]
                    clean_room_key = r_name.replace("号室", "")
                    
                    # SIMULATED PACKET INPUT: From your original file structure
                    simulated_packet = {
                        "room_id": r_id,
                        "room_number": clean_room_key,
                        "bpm": random.randint(65, 95) if random.random() > 0.05 else None,
                        "temp": round(random.uniform(21.0, 26.5), 1),
                        "humidity": round(random.uniform(40.0, 65.0), 1)
                    }
                    
                    # Phase 1: Data Validation Filtering
                    bpm = simulated_packet.get("bpm")
                    temp = simulated_packet.get("temp")
                    humidity = simulated_packet.get("humidity")
                    
                    if bpm is None or temp is None or humidity is None:
                        continue  # Drop frame instantly
                    
                    # Fetch active resident mapping context safely
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
                    
                    # Phase 2: Push to Cache Manager
                    self.cache.update_room(clean_room_key, {
                        "name": p_name,
                        "age": p_age,
                        "bpm": bpm,
                        "temp": temp,
                        "humidity": humidity,
                        "date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                    # Phase 3: Accumulate into buffers
                    if r_id not in self.raw_memory_buffers:
                        self.raw_memory_buffers[r_id] = []
                    self.raw_memory_buffers[r_id].append({"bpm": bpm, "temp": temp, "humidity": humidity})
                
                # Phase 4: Time Transition Tracking
                now = datetime.datetime.now()
                current_minute = now.minute
                current_hour = now.hour
                
                if self.last_processed_minute == -1:
                    self.last_processed_minute = current_minute
                    self.last_processed_hour = current_hour
                    
                if current_minute != self.last_processed_minute:
                    self._flush_minute_averages()
                    self.last_processed_minute = current_minute
                    
                if current_hour != self.last_processed_hour:
                    self._flush_hourly_averages(now)
                    self.last_processed_hour = current_hour
                    
            except Exception as e:
                print(f"Pipeline Engine Runtime Intercept: {e}")
                
            time.sleep(10)

    def _flush_minute_averages(self):
        """Reduces high-frequency frames to a single 1-minute averaged entry and cleans historical bloat."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for room_id, frames in list(self.raw_memory_buffers.items()):
            if not frames:
                continue
                
            avg_bpm = int(sum(f["bpm"] for f in frames) / len(frames))
            avg_temp = round(sum(f["temp"] for f in frames) / len(frames), 1)
            avg_humidity = round(sum(f["humidity"] for f in frames) / len(frames), 1)
            
            cursor.execute('''
                INSERT INTO room_live_buffer (room_id, bpm, temp, humidity, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (room_id, avg_bpm, avg_temp, avg_humidity, now_str))
            
            cursor.execute("DELETE FROM room_live_buffer WHERE timestamp < datetime('now', '-1 hour')")
            self.raw_memory_buffers[room_id] = []
            
        conn.commit()
        conn.close()

    def _flush_hourly_averages(self, current_time):
        """Calculates long-term history averages from the live minute records."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        top_of_hour_str = current_time.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("SELECT DISTINCT room_id FROM room_live_buffer")
        active_room_ids = [row[0] for row in cursor.fetchall()]
        
        for room_id in active_room_ids:
            cursor.execute('SELECT AVG(bpm), AVG(temp), AVG(humidity) FROM room_live_buffer WHERE room_id = ?', (room_id,))
            aggregated_res = cursor.fetchone()
            
            if aggregated_res and aggregated_res[0] is not None:
                cursor.execute('''
                    INSERT INTO room_historical_log (room_id, avg_bpm, avg_temp, avg_humidity, log_hour)
                    VALUES (?, ?, ?, ?, ?)
                ''', (room_id, int(aggregated_res[0]), round(aggregated_res[1], 1), round(aggregated_res[2], 1), top_of_hour_str))
                
        conn.commit()
        conn.close()