import os
import threading
from flask import Flask
from flask_bcrypt import Bcrypt

# Import our custom blueprints (the isolated route modules)
from auth_routes import auth_bp
from monitoring_routes import monitoring_bp
from patient_routes import patient_bp
from admin_routes import admin_bp

# Import our new OOP background engines and data vaults
from services import TelemetryCacheManager, IoTDataPipelineEngine
from sensor_manager import automated_csv_polling_worker, CSV_FOLDER

def create_app():
    """
    Application Factory Pattern.
    Initializes system-wide security middleware, maps state data vaults, 
    and registers decoupled route blueprints.
    """
    app = Flask(__name__)
    app.secret_key = 'carehouse_secret_signing_token_v1.3_core'
    
    # 1. Initialize Security Extension Engine
    bcrypt = Bcrypt(app)
    app.extensions['bcrypt'] = bcrypt  # Register to allow deep context lookup within blueprints
    
    # 2. Assert and Ensure File System Folders Exist
    if not os.path.exists(CSV_FOLDER):
        os.makedirs(CSV_FOLDER)
        
    # 3. Instantiate the OOP Global Telemetry Cache Data Vault
    telemetry_cache = TelemetryCacheManager()
    
    # Attach cache directly to application config so monitoring blueprints can reference it cleanly
    app.config['TELEMETRY_CACHE'] = telemetry_cache
    
    # 4. Register Modular Blueprints (Attaching your separate files to the web pipeline)
    app.register_blueprint(auth_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(admin_bp)
    
    # 5. Boot Up Background Worker Pipelines
    # Worker A: Hardware Poll Engine (reads incoming telemetry files from your CSV drop folder)
    threading.Thread(target=automated_csv_polling_worker, daemon=True).start()
    
    # Worker B: Time-Matching Math Pipeline Engine (aggregates and flushes real-time ticks to database boundaries)
    pipeline_worker = IoTDataPipelineEngine(telemetry_cache)
    threading.Thread(target=pipeline_worker.run_engine_loop, daemon=True).start()
    
    return app


# Application Entry Execution Vector
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)