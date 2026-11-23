from datetime import date

from flask import Blueprint, flash, redirect, render_template, url_for

from models import AlertLog, Attendance, Student
from services.email_service import audit_and_send_low_attendance_alerts
from utils.auth import login_required

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()
    all_students = Student.query.all()
    total_students = len(all_students)
    present_today = Attendance.query.filter_by(date=today, status="PRESENT").count()
    absent_today = Attendance.query.filter_by(date=today, status="ABSENT").count()
    total_records = Attendance.query.count()
    recent_records = Attendance.query.order_by(Attendance.date.desc(), Attendance.time.desc()).limit(8).all()

    # Identify defaulters (< 75% attendance)
    defaulters = [s for s in all_students if s.total_classes > 0 and s.attendance_percentage < 75.0]
    defaulters_count = len(defaulters)

    recent_alerts = AlertLog.query.order_by(AlertLog.sent_at.desc()).limit(6).all()

    chart_labels = ["Present Today", "Absent Today", "Below 75% Defaulters"]
    chart_data = [present_today, absent_today, defaulters_count]

    return render_template(
        "dashboard/index.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        total_records=total_records,
        recent_records=recent_records,
        defaulters=defaulters,
        defaulters_count=defaulters_count,
        recent_alerts=recent_alerts,
        chart_labels=chart_labels,
        chart_data=chart_data,
    )


@dashboard_bp.route("/send-batch-alerts", methods=["POST"])
@login_required
def send_batch_alerts():
    result = audit_and_send_low_attendance_alerts()
    sent = result["sent_count"]
    skipped = result["skipped_count"]
    flash(f"Batch low attendance warning completed: {sent} emails dispatched/logged, {skipped} skipped (due to cooldown or missing email).", "success")
    return redirect(url_for("dashboard.index"))
