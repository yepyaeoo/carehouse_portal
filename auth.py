from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("patient.dashboard"))
    return render_template("role_select.html")


@auth_bp.route("/login/<role>", methods=["GET", "POST"])
def login_page(role):
    if role not in ("admin", "patient"):
        return redirect(url_for("auth.index"))

    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("patient.dashboard"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user     = User.query.filter_by(username=username, role=role).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("patient.dashboard"))
        flash("Wrong username or password.")

    return render_template("login.html", role=role)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.index"))