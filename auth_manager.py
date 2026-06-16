import sqlite3
from functools import wraps
from flask import session, redirect, url_for, abort
from sensor_manager import DB_FILE

def login_required(role_target=None):
    """
    Decorator to protect server routes.
    If role_target='staff', only users with role=='staff' can pass.
    Otherwise, any authenticated user can enter.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged into session
            if 'user_id' not in session:
                return redirect(url_for('route_login_portal'))
            
            # Check role requirements if specified
            if role_target and session.get('role') != role_target:
                abort(403) # Forbidden access block
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def verify_user_credentials(username, password, bcrypt_instance):
    """
    Looks up username in database and matches the hash securely.
    Returns user dict on success, None on failure.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, username, password_hash, role, patient_id 
        FROM users WHERE username = ? LIMIT 1
    ''', (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        u_id, u_name, p_hash, u_role, p_id = row
        # Secure cryptographic check
        if bcrypt_instance.check_password_hash(p_hash, password):
            return {
                "user_id": u_id,
                "username": u_name,
                "role": u_role,
                "patient_id": p_id
            }
            
    return None