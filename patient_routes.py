import sqlite3
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, abort
from auth_manager import login_required
from sensor_manager import DB_FILE

# Initialize the patient-side workspace blueprint
patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/patient/notices')
@login_required()
def route_patient_notices():
    """
    Retrieves and displays institutional system notices targeted to this resident.
    Automatically marks fetched records as read in the view ledger.
    """
    p_id = session.get('patient_id')
    if not p_id: 
        abort(403)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Query notices intended for everyone or explicitly mapped to this individual patient
    cursor.execute('''
        SELECT notice_id, title, body, created_at FROM system_notices
        WHERE recipient_type = 'all' OR target_patient_id = ?
        ORDER BY notice_id DESC
    ''', (p_id,))
    notices = cursor.fetchall()
    
    # Mark newly rendered notices as acknowledged by this patient
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for row in notices:
        cursor.execute('''
            INSERT OR IGNORE INTO notice_views (notice_id, patient_id, viewed_at) 
            VALUES (?, ?, ?)
        ''', (row[0], p_id, now_str))
    
    conn.commit()
    conn.close()
    return render_template('patient_notices.html', notices=notices)


@patient_bp.route('/patient/mails', methods=['GET', 'POST'])
@login_required()
def route_patient_mails():
    """
    Manages interactive choice correspondence, custom patient survey questionnaires, 
    and lets residents submit answers back to the administration log.
    """
    p_id = session.get('patient_id')
    if not p_id: 
        abort(403)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Handle response feedback form processing
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
            pass  # Ignore if response record already exists
            
        return redirect(url_for('patient.route_patient_mails'))
        
    # Query all mail entries bound to this patient along with any previous response answers
    cursor.execute('''
        SELECT m.mail_id, m.title, m.body, m.response_type, m.choice_options, m.created_at, r.submitted_answer
        FROM patient_mails m
        LEFT JOIN mail_replies r ON m.mail_id = r.mail_id AND r.patient_id = ?
        WHERE m.target_patient_id = ? 
        ORDER BY m.mail_id DESC
    ''', (p_id, p_id))
    mails = cursor.fetchall()
    conn.close()
    
    return render_template('patient_mails.html', mails=mails)


@patient_bp.route('/patient/ai-assistant')
@login_required()
def route_patient_ai():
    """
    Renders the communication interface for the resident's personalized 
    AI interactive support workspace.
    """
    p_id = session.get('patient_id')
    if not p_id: 
        abort(403)
    
    p_name = session.get('username', '入居者')
    return render_template('patient_ai.html', patient_name=p_name)