from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from models import db, User, PatientProfile, Medicine, Assignment, Message
from functools import wraps

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            return redirect(url_for("patient.dashboard"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/admin/dashboard")
@login_required
@admin_required
def dashboard():
    return render_template("admin_dashboard.html")


@admin_bp.route("/admin/patients")
@login_required
@admin_required
def patients():
    all_patients = User.query.filter_by(role="patient").all()
    return render_template("admin_patients.html", patients=all_patients)


@admin_bp.route("/admin/patients/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_patient():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        name     = request.form["name"]
        age      = request.form["age"]
        weight   = request.form["weight"]
        height   = request.form["height"]
        bp       = request.form["blood_pressure"]

        if User.query.filter_by(username=username).first():
            flash("Username already taken.")
            return redirect(url_for("admin.add_patient"))

        user = User(
            username      = username,
            password_hash = generate_password_hash(password),
            role          = "patient"
        )
        db.session.add(user)
        db.session.flush()

        profile = PatientProfile(
            user_id        = user.id,
            name           = name,
            age            = int(age),
            weight_kg      = float(weight),
            height_cm      = float(height),
            blood_pressure = bp
        )
        db.session.add(profile)
        db.session.commit()
        flash(f"Patient {name} added successfully.")
        return redirect(url_for("admin.patients"))

    return render_template("admin_add_patient.html")


@admin_bp.route("/admin/patients/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_patient(user_id):
    user    = User.query.get(user_id)
    profile = user.profile

    if not user or user.role != "patient":
        flash("Patient not found.")
        return redirect(url_for("admin.patients"))

    if request.method == "POST":
        user.username          = request.form["username"]
        profile.name           = request.form["name"]
        profile.age            = int(request.form["age"])
        profile.weight_kg      = float(request.form["weight"])
        profile.height_cm      = float(request.form["height"])
        profile.blood_pressure = request.form["blood_pressure"]

        new_password = request.form["password"]
        if new_password:
            user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        flash("Patient updated successfully.")
        return redirect(url_for("admin.patients"))

    return render_template("admin_edit_patient.html", user=user, profile=profile)


@admin_bp.route("/admin/patients/delete/<int:user_id>")
@login_required
@admin_required
def delete_patient(user_id):
    user = User.query.get(user_id)
    if user and user.role == "patient":
        db.session.delete(user)
        db.session.commit()
        flash("Patient removed.")
    return redirect(url_for("admin.patients"))


@admin_bp.route("/admin/medicines", methods=["GET", "POST"])
@login_required
@admin_required
def medicines():
    if request.method == "POST":
        name        = request.form["name"]
        description = request.form["description"]

        medicine = Medicine(name=name, description=description)
        db.session.add(medicine)
        db.session.commit()
        flash("Medicine added successfully.")
        return redirect(url_for("admin.medicines"))

    all_medicines = Medicine.query.all()
    return render_template("admin_medicines.html", medicines=all_medicines)


@admin_bp.route("/admin/delete_medicine/<int:medicine_id>")
@login_required
@admin_required
def delete_medicine(medicine_id):
    medicine = Medicine.query.get(medicine_id)
    if medicine:
        db.session.delete(medicine)
        db.session.commit()
        flash("Medicine removed.")
    return redirect(url_for("admin.medicines"))


@admin_bp.route("/admin/assign", methods=["GET", "POST"])
@login_required
@admin_required
def assign():
    if request.method == "POST":
        patient_id    = request.form["patient_id"]
        medicine_id   = request.form["medicine_id"]
        dosage        = request.form["dosage"]
        schedule_time = request.form["schedule_time"]
        day_of_week   = request.form["day_of_week"]

        assignment = Assignment(
            patient_id    = patient_id,
            medicine_id   = medicine_id,
            dosage        = dosage,
            schedule_time = schedule_time,
            day_of_week   = day_of_week
        )
        db.session.add(assignment)
        db.session.commit()
        flash("Medicine assigned successfully.")
        return redirect(url_for("admin.dashboard"))

    patients  = User.query.filter_by(role="patient").all()
    medicines = Medicine.query.all()
    return render_template("admin_assign.html",
                           patients=patients,
                           medicines=medicines)


@admin_bp.route("/admin/delete_assignment/<int:assignment_id>")
@login_required
@admin_required
def delete_assignment(assignment_id):
    assignment = Assignment.query.get(assignment_id)
    if assignment:
        db.session.delete(assignment)
        db.session.commit()
        flash("Assignment removed.")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/admin/messages", methods=["GET", "POST"])
@login_required
@admin_required
def messages():
    if request.method == "POST":
        recipient_id = request.form["recipient_id"]
        subject      = request.form["subject"]
        body         = request.form["body"]

        message = Message(
            recipient_id = recipient_id,
            subject      = subject,
            body         = body
        )
        db.session.add(message)
        db.session.commit()
        flash("Message sent.")
        return redirect(url_for("admin.messages"))

    patients = User.query.filter_by(role="patient").all()
    return render_template("admin_messages.html", patients=patients)


@admin_bp.route("/admin/assignments")
@login_required
@admin_required
def assignments():
    all_patients = User.query.filter_by(role="patient").all()
    return render_template("admin_assignments.html", patients=all_patients)