from flask import Flask
from flask_login import LoginManager
from models import db, User

app = Flask(__name__)
app.config["SECRET_KEY"]              = "change-this-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medicine.db"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login_page"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from auth import auth_bp
from admin import admin_bp
from patient import patient_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(patient_bp)

if __name__ == "__main__":
    app.run(debug=True)