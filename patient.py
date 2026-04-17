from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Assignment, IntakeLog, Message
from datetime import date, datetime

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/patient/dashboard")
@login_required
def dashboard():
    unread = Message.query.filter_by(
        recipient_id = current_user.id,
        is_read      = False
    ).count()
    return render_template("patient_dashboard.html", unread=unread)


@patient_bp.route("/patient/schedule")
@login_required
def schedule():
    today    = date.today()
    day_name = today.strftime("%A")

    assignments = Assignment.query.filter_by(patient_id=current_user.id).all()

    schedule = []
    for assignment in assignments:
        if assignment.day_of_week == "Daily" or assignment.day_of_week == day_name:
            log = IntakeLog.query.filter_by(
                assignment_id = assignment.id,
                taken_date    = today
            ).first()
            schedule.append({
                "assignment": assignment,
                "log":        log,
                "taken":      log is not None
            })

    schedule.sort(key=lambda x: x["assignment"].schedule_time)

    week_logs = []
    for assignment in assignments:
        logs = IntakeLog.query.filter_by(
            assignment_id=assignment.id
        ).order_by(IntakeLog.taken_date.desc()).limit(7).all()
        week_logs.append({
            "assignment": assignment,
            "logs":       logs
        })

    return render_template("patient_schedule.html",
                           schedule=schedule,
                           week_logs=week_logs,
                           today=today)


@patient_bp.route("/patient/profile")
@login_required
def profile():
    return render_template("patient_profile.html", profile=current_user.profile)


@patient_bp.route("/patient/mailbox")
@login_required
def mailbox():
    messages = Message.query.filter_by(
        recipient_id=current_user.id
    ).order_by(Message.sent_at.desc()).all()

    for msg in messages:
        if not msg.is_read:
            msg.is_read = True
    db.session.commit()

    return render_template("patient_mailbox.html", messages=messages)


@patient_bp.route("/patient/take/<int:assignment_id>")
@login_required
def take_medicine(assignment_id):
    assignment = Assignment.query.get(assignment_id)

    if not assignment or assignment.patient_id != current_user.id:
        flash("Not allowed.")
        return redirect(url_for("patient.schedule"))

    today   = date.today()
    already = IntakeLog.query.filter_by(
        assignment_id = assignment_id,
        taken_date    = today
    ).first()

    if already:
        flash("Already marked as taken today.")
        return redirect(url_for("patient.schedule"))

    log = IntakeLog(
        assignment_id = assignment_id,
        taken_date    = today,
        taken_time    = datetime.now().strftime("%H:%M"),
        status        = "taken"
    )
    db.session.add(log)
    db.session.commit()
    flash("Marked as taken.")
    return redirect(url_for("patient.schedule"))


@patient_bp.route("/patient/undo/<int:assignment_id>")
@login_required
def undo_medicine(assignment_id):
    assignment = Assignment.query.get(assignment_id)

    if not assignment or assignment.patient_id != current_user.id:
        flash("Not allowed.")
        return redirect(url_for("patient.schedule"))

    today = date.today()
    log   = IntakeLog.query.filter_by(
        assignment_id = assignment_id,
        taken_date    = today
    ).first()

    if log:
        db.session.delete(log)
        db.session.commit()
        flash("Marked as not taken.")

    return redirect(url_for("patient.schedule"))