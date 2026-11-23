import base64
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import or_

from extensions import db
from models import Attendance, Student
from services.face_service import recognize_image
from utils.auth import login_required
from utils.files import allowed_image, unique_filename

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.route("/take", methods=["GET", "POST"])
@login_required
def take():
    result = None
    if request.method == "POST":
        image = request.files.get("classroom_image")
        if not image or not image.filename:
            flash("Please upload a classroom image.", "danger")
            return render_template("attendance/take.html", result=None)
        if not allowed_image(image.filename):
            flash("Only JPG, PNG, JPEG, and WEBP files are allowed.", "danger")
            return render_template("attendance/take.html", result=None)
        upload_name = unique_filename(image.filename)
        upload_path = Path(current_app.config["UPLOAD_FOLDER"]) / upload_name
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(upload_path)
        try:
            result = recognize_image(upload_path, date.today(), method="upload")
            flash("Classroom attendance processed successfully.", "success")
            if result.summary.get("alerts_triggered", 0) > 0:
                flash(f"Notice: Automated warning email alerts were dispatched to {result.summary['alerts_triggered']} student(s) with attendance below 75%.", "warning")
        except Exception as exc:
            current_app.logger.exception("Attendance recognition failed")
            flash(f"Recognition failed: {exc}", "danger")
    return render_template("attendance/take.html", result=result)


@attendance_bp.route("/webcam", methods=["POST"])
@login_required
def webcam():
    payload = request.get_json(silent=True) or {}
    data_url = payload.get("image", "")
    if "," not in data_url:
        return jsonify({"ok": False, "message": "Invalid camera image."}), 400
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return jsonify({"ok": False, "message": "Could not decode camera image."}), 400
    upload_name = f"webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    upload_path = Path(current_app.config["UPLOAD_FOLDER"]) / upload_name
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(raw)
    try:
        result = recognize_image(upload_path, date.today(), method="webcam")
    except Exception as exc:
        current_app.logger.exception("Webcam recognition failed")
        return jsonify({"ok": False, "message": str(exc)}), 500
    return jsonify(
        {
            "ok": True,
            "recognized": result.recognized,
            "unknown_count": result.unknown_count,
            "summary": result.summary,
            "processed_image": url_for("static", filename=result.processed_image) if result.processed_image else None,
        }
    )


@attendance_bp.route("/history")
@login_required
def history():
    query = Attendance.query.join(Student)
    selected_date = request.args.get("date", "").strip()
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().upper()
    page = request.args.get("page", 1, type=int)

    if selected_date:
        try:
            query = query.filter(Attendance.date == datetime.strptime(selected_date, "%Y-%m-%d").date())
        except ValueError:
            flash("Invalid date filter.", "warning")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Student.full_name.ilike(like), Student.roll_number.ilike(like)))
    if status_filter in ("PRESENT", "ABSENT"):
        query = query.filter(Attendance.status == status_filter)

    records = query.order_by(Attendance.date.desc(), Attendance.time.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "attendance/history.html",
        records=records,
        selected_date=selected_date,
        search=search,
        status_filter=status_filter,
    )


@attendance_bp.route("/delete/<int:record_id>", methods=["POST"])
@login_required
def delete_record(record_id):
    record = Attendance.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    flash("Attendance record deleted.", "info")
    return redirect(url_for("attendance.history"))
