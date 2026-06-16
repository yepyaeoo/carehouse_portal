import sqlite3
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from auth_manager import login_required
from sensor_manager import DB_FILE

# Initialize the staff operations blueprint
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/dashboard', methods=['GET'])
@login_required(role_target='staff')
def route_admin_dashboard():
    """
    Core operations control grid menu display.
    """
    return render_template('admin_dashboard.html')


@admin_bp.route('/admin/patients', methods=['GET', 'POST'])
@login_required(role_target='staff')
def route_manage_patients():
    """
    Dedicated Resident Management Portal.
    Handles adding new profiles, recording physical metrics, and assigning open rooms.
    """
    conn = sqlite3.connect(DB_FILE)
    
    if request.method == 'POST':
        # Extract fields matching your manage_patients.html form inputs
        name = request.form.get('patient_name')
        age = request.form.get('age')
        height = request.form.get('height')
        weight = request.form.get('weight')
        assigned_date = request.form.get('assigned_date')  # From HTML date input field
        room_id = request.form.get('room_id')
        
        # Generate current time string to satisfy the NOT NULL constraint on patients.created_at
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor = conn.cursor()
        # 1. Insert patient data records into the ledger system including created_at timestamp
        cursor.execute('''
            INSERT INTO patients (patient_name, age, height, weight, created_at) 
            VALUES (?, ?, ?, ?, ?)
        ''', (name, int(age), float(height), float(weight), now_str))
        new_patient_id = cursor.lastrowid
        
        # 2. Map their active room location assignment if provided
        # FIXED: Added assigned_at column and passed assigned_date to clear the NOT NULL constraint error
        if room_id:
            cursor.execute('''
                INSERT INTO room_assignments (room_id, patient_id, assigned_at, is_active) 
                VALUES (?, ?, ?, 1)
            ''', (int(room_id), new_patient_id, assigned_date))
            
        conn.commit()
        conn.close()
        return redirect(url_for('admin.route_manage_patients'))
        
    # GET Request Processing: Gather view payloads
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # FIXED: Replaced fallback '--' with real ra.assigned_at string to match the database configuration
    cursor.execute('''
        SELECT p.patient_id, p.patient_name, p.age, p.height, p.weight, ra.assigned_at AS assigned_date, r.room_name 
        FROM patients p
        LEFT JOIN room_assignments ra ON p.patient_id = ra.patient_id AND ra.is_active = 1
        LEFT JOIN rooms r ON ra.room_id = r.room_id
        ORDER BY p.patient_id DESC
    ''')
    roster = cursor.fetchall()
    
    # Fetch unallocated rooms loop data matrix
    cursor.execute('''
        SELECT r.room_id, r.room_name FROM rooms r
        WHERE r.room_id NOT IN (SELECT room_id FROM room_assignments WHERE is_active = 1)
    ''')
    vacant_rooms = cursor.fetchall()
    conn.close()
    
    return render_template('manage_patients.html', roster=roster, vacant_rooms=vacant_rooms)


@admin_bp.route('/admin/patients/discharge/<int:patient_id>', methods=['GET'])
@login_required(role_target='staff')
def route_discharge_patient(patient_id):
    """
    Deactivates active room maps to complete a discharge event safely.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE room_assignments SET is_active = 0 WHERE patient_id = ?", (patient_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin.route_manage_patients'))


@admin_bp.route('/admin/communication', methods=['GET', 'POST'])
@login_required(role_target='staff')
def route_admin_communication():
    """
    Unified Communication Control Hub.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        selected_patients = request.form.getlist('selected_patients')
        title = request.form.get('title')
        body = request.form.get('body')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if not selected_patients:
            flash("送信エラー：対象の入居者様が選択されていません。", "error")
            return redirect(url_for('admin.route_admin_communication'))
            
        if form_type == 'notice':
            for p_id in selected_patients:
                cursor.execute('''
                    INSERT INTO system_notices (title, body, recipient_type, target_patient_id, created_at)
                    VALUES (?, ?, 'individual', ?, ?)
                ''', (title, body, int(p_id), now_str))
            conn.commit()
            
        elif form_type == 'mail':
            resp_type = request.form.get('response_type')
            options = request.form.get('choice_options') if resp_type == 'choices' else None
            for p_id in selected_patients:
                cursor.execute('''
                    INSERT INTO patient_mails (target_patient_id, title, body, response_type, choice_options, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (int(p_id), title, body, resp_type, options, now_str))
            conn.commit()
            
        conn.close()
        return redirect(url_for('admin.route_admin_communication'))
        
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, patient_name FROM patients ORDER BY patient_id ASC")
    patients = cursor.fetchall()
    
    cursor.execute('''
        SELECT n.notice_id, n.title, p.patient_name, n.created_at 
        FROM system_notices n
        LEFT JOIN patients p ON n.target_patient_id = p.patient_id
        ORDER BY n.created_at DESC LIMIT 50
    ''')
    notices = cursor.fetchall()
    
    cursor.execute('''
        SELECT m.mail_id, m.title, p.patient_name, m.created_at, r.submitted_answer 
        FROM patient_mails m
        JOIN patients p ON m.target_patient_id = p.patient_id
        LEFT JOIN mail_replies r ON m.mail_id = r.mail_id AND m.target_patient_id = r.patient_id
        ORDER BY m.created_at DESC LIMIT 50
    ''')
    mails = cursor.fetchall()
    conn.close()
    
    return render_template('admin_communication.html', patients=patients, notices=notices, mails=mails)