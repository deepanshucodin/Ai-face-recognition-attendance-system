from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from models import Attendance, Student
from services.email_service import send_low_attendance_email

student_bp = Blueprint("student_portal", __name__, url_prefix="/student")


def student_login_required(view_func):
    """Decorator ensuring that a student is signed in."""
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("student_id"):
            flash("Please enter your Roll Number to access your attendance portal.", "warning")
            return redirect(url_for("auth.login", tab="student"))
        return view_func(*args, **kwargs)

    return wrapped_view


@student_bp.route("/dashboard")
@student_login_required
def dashboard():
    student_id = session.get("student_id")
    student = Student.query.get_or_404(student_id)

    records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc(), Attendance.time.desc()).all()

    total = len(records)
    present = len([r for r in records if r.status == "PRESENT"])
    absent = len([r for r in records if r.status == "ABSENT"])
    percentage = round((present / total) * 100, 2) if total > 0 else 100.0

    # Calculate how many consecutive classes student must attend to reach 75%
    classes_needed = 0
    if total > 0 and percentage < 75.0:
        # (present + x) / (total + x) >= 0.75
        # present + x >= 0.75*total + 0.75*x
        # 0.25*x >= 0.75*total - present
        # x >= (0.75*total - present) / 0.25
        classes_needed = max(1, int((0.75 * total - present) / 0.25) + 1)

    return render_template(
        "student/dashboard.html",
        student=student,
        records=records,
        total=total,
        present=present,
        absent=absent,
        percentage=percentage,
        classes_needed=classes_needed,
    )


@student_bp.route("/resend-warning", methods=["POST"])
@student_login_required
def resend_warning():
    student_id = session.get("student_id")
    student = Student.query.get_or_404(student_id)

    if student.attendance_percentage >= 75.0:
        flash("Your attendance is currently above 75%. No warning is needed.", "info")
        return redirect(url_for("student_portal.dashboard"))

    success, msg = send_low_attendance_email(student, force=True)
    if success:
        flash("Official attendance shortage advisory email dispatched to your inbox.", "success")
    else:
        flash(f"Could not dispatch email: {msg}", "warning")
    return redirect(url_for("student_portal.dashboard"))
