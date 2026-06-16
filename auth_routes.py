import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, session
from auth_manager import verify_user_credentials, login_required
from sensor_manager import DB_FILE

# Define the blueprint. This assigns these routes to a self-contained module.
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def route_login_portal():
    """
    Handles user login authentication.
    Verifies submitted credentials against security profiles and maps 
    session attributes (role, user identity, patient tracking IDs).
    """
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        
        # Access the encryption verification utility imported from auth_manager
        # We pass the app's bcrypt object via the current_app context or global reference
        from flask import current_app
        bcrypt = current_app.extensions['bcrypt']
        
        prof = verify_user_credentials(u, p, bcrypt)
        if prof:
            session['user_id'] = prof['user_id']
            session['username'] = prof['username']
            session['role'] = prof['role']
            session['patient_id'] = prof['patient_id']
            
            # Staff roles branch out to administration; residents go directly to room monitoring dashboards
            if prof['role'] == 'staff':
                return redirect(url_for('admin.route_admin_dashboard'))
            else:
                return redirect(url_for('monitoring.route_room_detail', room_number=403))
                
    return render_template('login.html')


@auth_bp.route('/logout')
def route_logout_action():
    """
    Clears the active session container memory to securely sign out users,
    then drops them back at the central login gate.
    """
    session.clear()
    return redirect(url_for('auth.route_login_portal'))


@auth_bp.route('/rooms')
@login_required(role_target='staff')
def route_room_directory():
    """
    Displays a comprehensive overview of building layouts and total active resident numbers.
    Restricted entirely to healthcare staff.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Aggregates room allocation logs dynamically
    cursor.execute('''
        SELECT r.room_name, 
               (SELECT COUNT(*) FROM room_assignments ra 
                WHERE ra.room_id = r.room_id AND ra.is_active = 1) 
        FROM rooms r
    ''')
    room_data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    return render_template('rooms.html', room_data=room_data)