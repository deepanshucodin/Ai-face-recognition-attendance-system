from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models import Admin, Student

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, redirect to respective dashboard
    if session.get("admin_id"):
        return redirect(url_for("dashboard.index"))
    if session.get("student_id"):
        return redirect(url_for("student_portal.dashboard"))

    active_tab = request.args.get("tab", "admin")

    if request.method == "POST":
        login_type = request.form.get("login_type", "admin")

        if login_type == "student":
            active_tab = "student"
            roll_number = request.form.get("roll_number", "").strip().upper()
            password = request.form.get("student_password", "").strip()

            if not roll_number:
                flash("Please enter your Roll Number.", "danger")
                return render_template("auth/login.html", active_tab=active_tab)

            student = Student.query.filter(Student.roll_number.ilike(roll_number)).first()
            if not student:
                flash(f"No student record found with Roll Number '{roll_number}'.", "danger")
                return render_template("auth/login.html", active_tab=active_tab)

            # Check password if configured, or default to roll number
            if student.password_hash and password:
                if not student.check_password(password):
                    flash("Incorrect student password.", "danger")
                    return render_template("auth/login.html", active_tab=active_tab)
            elif student.password_hash and not password:
                flash("This student account requires a password. Please enter it.", "warning")
                return render_template("auth/login.html", active_tab=active_tab)

            session.clear()
            session["student_id"] = student.id
            session["student_name"] = student.full_name
            session["student_roll"] = student.roll_number
            flash(f"Welcome, {student.full_name}! Here is your attendance overview.", "success")
            return redirect(url_for("student_portal.dashboard"))

        else:
            active_tab = "admin"
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            admin = Admin.query.filter_by(username=username).first()
            if admin and admin.check_password(password):
                session.clear()
                session["admin_id"] = admin.id
                session["admin_username"] = admin.username
                flash("Welcome back, Administrator.", "success")
                return redirect(url_for("dashboard.index"))
            flash("Invalid administrator username or password.", "danger")

    return render_template("auth/login.html", active_tab=active_tab)


@auth_bp.route("/logout")
def logout():
    was_student = bool(session.get("student_id"))
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login", tab="student" if was_student else "admin"))
