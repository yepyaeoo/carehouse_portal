from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(10), nullable=False)

    assignments   = db.relationship("Assignment", backref="patient", lazy=True)
    profile       = db.relationship("PatientProfile", backref="user", uselist=False)
    messages      = db.relationship("Message", backref="recipient", lazy=True)


class PatientProfile(db.Model):
    __tablename__ = "patient_profiles"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name           = db.Column(db.String(100), nullable=False)
    age            = db.Column(db.Integer)
    weight_kg      = db.Column(db.Float)
    height_cm      = db.Column(db.Float)
    blood_pressure = db.Column(db.String(20))


class Medicine(db.Model):
    __tablename__ = "medicines"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))

    assignments = db.relationship("Assignment", backref="medicine", lazy=True)


class Assignment(db.Model):
    __tablename__ = "assignments"

    id            = db.Column(db.Integer, primary_key=True)
    patient_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    medicine_id   = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    dosage        = db.Column(db.String(50))
    schedule_time = db.Column(db.String(5), nullable=False)
    day_of_week   = db.Column(db.String(10), nullable=False)
    start_date    = db.Column(db.Date, default=datetime.today)

    logs          = db.relationship("IntakeLog", backref="assignment", lazy=True)


class IntakeLog(db.Model):
    __tablename__ = "intake_log"

    id            = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    taken_date    = db.Column(db.Date, nullable=False)
    taken_time    = db.Column(db.String(5))
    status        = db.Column(db.String(10), default="taken")


class Message(db.Model):
    __tablename__ = "messages"

    id           = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject      = db.Column(db.String(200), nullable=False)
    body         = db.Column(db.Text, nullable=False)
    sent_at      = db.Column(db.DateTime, default=datetime.utcnow)
    is_read      = db.Column(db.Boolean, default=False)