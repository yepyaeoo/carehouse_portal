import sqlite3

from flask import Blueprint, render_template, request, session, abort, current_app

from auth_manager import login_required

from sensor_manager import DB_FILE

from services import CareHouseDatabaseService



# Define the monitoring blueprint segment

monitoring_bp = Blueprint('monitoring', __name__)



@monitoring_bp.route('/room/<int:room_number>')

@login_required()

def route_room_detail(room_number):

    """

    Renders the immediate, real-time vital dashboard tracking feed.

    Leverages our OOP TelemetryCacheManager to perform high-speed reads

    without stalling database engine connections.

    """

    if room_number != 403:

        abort(404)

       

    formatted_room_name = f"{room_number}号室"

    clean_key = str(room_number)

   

    # Safely pull the telemetry cache instance registered on the shared application core

    cache_service = current_app.config['TELEMETRY_CACHE']

   

    # 1. Direct Realtime Fast Read Processing Logic

    if cache_service.has_room(clean_key):

        cached_stream = cache_service.get_room(clean_key)

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

       

    # Utilize our OOP service to gather dynamic notification counts for the patient panel badge alert layout

    badge_payload = CareHouseDatabaseService.get_patient_badge_counts(data_payload["patient_id"])

   

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





@monitoring_bp.route('/room/<int:room_number>/history')

@login_required()

def route_room_history(room_number):

    """

    Renders long term analytics charts.

    Dynamically swaps queries on time boundaries to balance server compute overheads.

    """

    if session.get('role') == 'patient' and room_number != 403:

        abort(403)

       

    f_room_name = f"{room_number}号室"

    time_range = request.args.get('range', '1h')

   

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

   

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

        "current_range": time_range

    }

   

    return render_template(

        'room_history.html',

        room_number=room_number,

        patient_name=p_name,

        history=history_payload

    ) 

