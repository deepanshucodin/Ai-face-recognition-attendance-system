import re
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from extensions import db
from models import FaceEncoding, Student
from services.email_service import send_low_attendance_email
from services.face_service import create_encoding_from_image, serialize_encoding
from utils.auth import login_required
from utils.files import allowed_image, safe_student_folder, unique_filename

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@login_required
def list_students():
    students = Student.query.order_by(Student.created_at.desc()).all()
    return render_template("students/list.html", students=students)


@students_bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip().upper()
        department = request.form.get("department", "").strip()
        year_semester = request.form.get("year_semester", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        files = request.files.getlist("images")

        if not all([full_name, roll_number, department, year_semester]):
            flash("Name, Roll Number, Department, and Semester are required.", "danger")
            return render_template("students/register.html")

        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Please enter a valid email address.", "danger")
            return render_template("students/register.html")

        if Student.query.filter_by(roll_number=roll_number).first():
            flash(f"A student with Roll Number '{roll_number}' already exists.", "danger")
            return render_template("students/register.html")

        if not files or not any(file.filename for file in files):
            flash("Upload at least one clear facial image.", "danger")
            return render_template("students/register.html")

        folder_name = safe_student_folder(full_name, roll_number)
        student_dir = Path(current_app.config["REGISTERED_FACES_FOLDER"]) / folder_name
        student_dir.mkdir(parents=True, exist_ok=True)

        student = Student(
            full_name=full_name,
            roll_number=roll_number,
            department=department,
            year_semester=year_semester,
            email=email if email else None,
            image_folder=f"registered_faces/{folder_name}",
        )
        if password:
            student.set_password(password)

        db.session.add(student)
        db.session.flush()

        valid_count = 0
        errors = []
        for file in files:
            if not file.filename:
                continue
            if not allowed_image(file.filename):
                errors.append(f"{file.filename}: unsupported file type")
                continue
            saved_name = unique_filename(file.filename)
            saved_path = student_dir / saved_name
            file.save(saved_path)
            try:
                encoding = create_encoding_from_image(saved_path)
            except ValueError as exc:
                saved_path.unlink(missing_ok=True)
                errors.append(f"{file.filename}: {exc}")
                continue
            db.session.add(
                FaceEncoding(
                    student_id=student.id,
                    encoding=serialize_encoding(encoding),
                    image_path=f"registered_faces/{folder_name}/{saved_name}",
                )
            )
            valid_count += 1

        if valid_count == 0:
            db.session.rollback()
            flash("Registration failed. No valid single-face image was detected.", "danger")
            for error in errors[:3]:
                flash(error, "warning")
            return render_template("students/register.html")

        db.session.commit()
        flash(f"Student '{full_name}' registered successfully with {valid_count} face encoding(s).", "success")
        for error in errors[:5]:
            flash(error, "warning")
        return redirect(url_for("students.list_students"))

    return render_template("students/register.html")


@students_bp.route("/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "POST":
        student.full_name = request.form.get("full_name", student.full_name).strip()
        student.department = request.form.get("department", student.department).strip()
        student.year_semester = request.form.get("year_semester", student.year_semester).strip()
        email = request.form.get("email", "").strip().lower()
        if email:
            student.email = email
        new_password = request.form.get("password", "").strip()
        if new_password:
            student.set_password(new_password)

        # Uploading extra face angles for accuracy
        files = request.files.getlist("images")
        if files and any(f.filename for f in files):
            folder_name = safe_student_folder(student.full_name, student.roll_number)
            student_dir = Path(current_app.config["REGISTERED_FACES_FOLDER"]) / folder_name
            student_dir.mkdir(parents=True, exist_ok=True)
            for file in files:
                if file.filename and allowed_image(file.filename):
                    saved_name = unique_filename(file.filename)
                    saved_path = student_dir / saved_name
                    file.save(saved_path)
                    try:
                        encoding = create_encoding_from_image(saved_path)
                        db.session.add(
                            FaceEncoding(
                                student_id=student.id,
                                encoding=serialize_encoding(encoding),
                                image_path=f"registered_faces/{folder_name}/{saved_name}",
                            )
                        )
                    except Exception:
                        saved_path.unlink(missing_ok=True)

        db.session.commit()
        flash(f"Student {student.roll_number} profile updated.", "success")
        return redirect(url_for("students.list_students"))

    return render_template("students/edit.html", student=student)


@students_bp.route("/send-warning/<int:student_id>", methods=["POST"])
@login_required
def send_warning(student_id):
    student = Student.query.get_or_404(student_id)
    success, msg = send_low_attendance_email(student, force=True)
    if success:
        flash(f"Warning email sent to {student.full_name} ({student.email}).", "success")
    else:
        flash(f"Alert could not be sent: {msg}", "warning")
    return redirect(url_for("students.list_students"))


@students_bp.route("/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash(f"Student {student.full_name} deleted.", "info")
    return redirect(url_for("students.list_students"))
