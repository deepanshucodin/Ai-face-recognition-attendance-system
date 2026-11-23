import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from flask import current_app

from extensions import db
from models import AlertLog, Student

logger = logging.getLogger("faceattend.email")


def generate_warning_email_html(student: Student, current_percentage: float) -> str:
    """Generates a professional academic warning letter in responsive HTML."""
    total = student.total_classes
    present = student.present_count
    absent = student.absent_count
    needed_for_75 = max(0, int((0.75 * total - present) / 0.25) + 1) if total > 0 else 0

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Urgent: Low Attendance Warning</title>
    <style>
        body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; color: #1e293b; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
        .header {{ background: linear-gradient(135deg, #b91c1c 0%, #dc2626 100%); color: #ffffff; padding: 32px 24px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
        .header p {{ margin: 8px 0 0; opacity: 0.9; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
        .content {{ padding: 32px 28px; }}
        .alert-box {{ background: #fef2f2; border-left: 4px solid #ef4444; padding: 18px; border-radius: 6px; margin: 20px 0; }}
        .alert-box strong {{ color: #991b1b; display: block; font-size: 16px; margin-bottom: 4px; }}
        .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 24px 0; }}
        .stat-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }}
        .stat-card .value {{ font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px; }}
        .stat-card .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600; }}
        .percentage-badge {{ font-size: 32px; font-weight: 900; color: #dc2626; }}
        .footer {{ background: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        .button {{ display: inline-block; background: #dc2626; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; margin-top: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OFFICIAL ATTENDANCE WARNING</h1>
            <p>Academic Affairs & Attendance Monitoring Cell</p>
        </div>
        <div class="content">
            <p>Dear <strong>{student.full_name}</strong> (Roll No: <strong>{student.roll_number}</strong>),</p>
            
            <div class="alert-box">
                <strong>CRITICAL NOTICE: ATTENDANCE BELOW MANDATORY 75%</strong>
                Your cumulative classroom attendance has fallen below the university mandated minimum threshold of 75.0%.
            </div>

            <div style="text-align: center; margin: 20px 0;">
                <div class="stat-card" style="display: inline-block; min-width: 200px; border-color: #fecaca; background: #fff5f5;">
                    <div class="label">Current Attendance Percentage</div>
                    <div class="percentage-badge">{current_percentage}%</div>
                    <div style="font-size: 12px; color: #dc2626; font-weight: 600;">Threshold: 75.0%</div>
                </div>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px 0; color: #64748b;">Department:</td>
                    <td style="padding: 10px 0; font-weight: 600; text-align: right;">{student.department}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px 0; color: #64748b;">Semester / Year:</td>
                    <td style="padding: 10px 0; font-weight: 600; text-align: right;">{student.year_semester}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px 0; color: #64748b;">Total Classes Conducted:</td>
                    <td style="padding: 10px 0; font-weight: 600; text-align: right;">{total}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px 0; color: #64748b;">Classes Attended:</td>
                    <td style="padding: 10px 0; font-weight: 600; text-align: right; color: #16a34a;">{present}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px 0; color: #64748b;">Classes Missed:</td>
                    <td style="padding: 10px 0; font-weight: 600; text-align: right; color: #dc2626;">{absent}</td>
                </tr>
            </table>

            <h3 style="font-size: 16px; margin-top: 24px; color: #0f172a;">Consequences of Attendance Shortage:</h3>
            <ul style="color: #475569; padding-left: 20px; line-height: 1.6;">
                <li>As per academic regulations, candidates with less than <strong>75% attendance</strong> will be debarred from appearing in the Semester End Examinations.</li>
                <li>Internal assessment marks and hall ticket issuance may be withheld.</li>
            </ul>

            <h3 style="font-size: 16px; margin-top: 20px; color: #0f172a;">Recommended Immediate Action:</h3>
            <p style="color: #475569; line-height: 1.6;">
                You are advised to immediately report to your Department Head / Faculty Advisor to discuss your attendance shortage. If your absence was due to medical or official grounds, please submit verified supporting documentation within 3 working days.
            </p>
        </div>
        <div class="footer">
            <p>This is an automated academic alert generated by the AI Face Recognition Attendance System.</p>
            <p>&copy; {datetime.utcnow().year} Academic Department. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


def generate_warning_email_text(student: Student, current_percentage: float) -> str:
    """Generates plain text fallback email."""
    return f"""OFFICIAL ATTENDANCE WARNING - LOW ATTENDANCE ALERT

Dear {student.full_name} (Roll No: {student.roll_number}),

CRITICAL NOTICE: Your current classroom attendance has dropped to {current_percentage}%, which is BELOW the mandatory 75.0% requirement.

Academic Summary:
- Department: {student.department}
- Semester/Year: {student.year_semester}
- Total Classes: {student.total_classes}
- Classes Present: {student.present_count}
- Classes Absent: {student.absent_count}
- Attendance: {current_percentage}%

Students with attendance below 75% are ineligible to appear in Semester Final Examinations according to university regulations.

Please contact your Department Head / Faculty Advisor immediately to rectify your attendance status.

This is an automated notification from FaceAttend AI System.
"""


def send_low_attendance_email(student: Student, force: bool = False) -> tuple[bool, str]:
    """
    Sends an automated low attendance warning email to the student if attendance < 75%.
    Includes cooldown protection (does not spam more than once every 18 hours unless forced).
    Supports live SMTP and graceful simulation/file-logging fallback.
    """
    if not current_app.config.get("MAIL_ALERT_ENABLED", True):
        return False, "Automated email alerts are disabled in configuration."

    if not student.email or "@" not in student.email:
        logger.warning(f"Student {student.roll_number} has no valid email registered.")
        return False, f"Student {student.roll_number} has no email address configured."

    current_percentage = student.attendance_percentage
    threshold = current_app.config.get("LOW_ATTENDANCE_THRESHOLD", 75.0)

    if current_percentage >= threshold and not force:
        return False, f"Attendance is {current_percentage}%, which meets the {threshold}% threshold."

    # Cooldown check: max 1 warning every 18 hours unless force=True
    if not force and student.last_alert_sent:
        elapsed = datetime.utcnow() - student.last_alert_sent
        if elapsed < timedelta(hours=18):
            return False, f"Warning already sent {elapsed.seconds // 3600} hours ago. Cooldown active."

    subject = f"URGENT: Low Attendance Warning ({current_percentage}%) - {student.full_name} [{student.roll_number}]"
    html_content = generate_warning_email_html(student, current_percentage)
    text_content = generate_warning_email_text(student, current_percentage)

    mail_server = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    mail_port = current_app.config.get("MAIL_PORT", 587)
    mail_user = current_app.config.get("MAIL_USERNAME", "")
    mail_pass = current_app.config.get("MAIL_PASSWORD", "")
    sender_email = current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@faceattend.edu")
    sender_name = current_app.config.get("MAIL_SENDER_NAME", "College Academic Department")

    status = "SIMULATED"
    dispatch_message = ""

    # Live SMTP delivery if credentials provided
    if mail_user and mail_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender_email}>"
            msg["To"] = student.email
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
                if current_app.config.get("MAIL_USE_TLS", True):
                    server.starttls()
                server.login(mail_user, mail_pass)
                server.sendmail(sender_email, [student.email], msg.as_string())

            status = "SENT"
            dispatch_message = f"Live email successfully dispatched to {student.email} via {mail_server}."
            logger.info(dispatch_message)
        except Exception as exc:
            logger.exception(f"SMTP delivery failed to {student.email}: {exc}")
            status = "FAILED"
            dispatch_message = f"SMTP error: {exc}. Logged to local alerts."

    # If SMTP is not configured or failed, simulate & log cleanly to file
    if status in ("SIMULATED", "FAILED"):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        alert_log_file = log_dir / "email_alerts.log"
        with open(alert_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n")
            f.write(f"TIMESTAMP: {datetime.utcnow().isoformat()}Z\n")
            f.write(f"TO: {student.email} ({student.full_name} - {student.roll_number})\n")
            f.write(f"STATUS: {status}\n")
            f.write(f"SUBJECT: {subject}\n")
            f.write(f"PERCENTAGE: {current_percentage}%\n")
            f.write(f"{text_content}\n")
            f.write(f"{'='*70}\n")

        if status == "SIMULATED":
            dispatch_message = f"Alert simulated & logged to logs/email_alerts.log (Configure SMTP credentials in .env to send live emails)."

    # Record in database
    alert_record = AlertLog(
        student_id=student.id,
        recipient_email=student.email,
        attendance_percentage=current_percentage,
        subject=subject,
        message_snippet=f"Attendance at {current_percentage}%, below 75% threshold.",
        status=status,
    )
    db.session.add(alert_record)
    student.last_alert_sent = datetime.utcnow()
    db.session.commit()

    return True, dispatch_message


def audit_and_send_low_attendance_alerts() -> dict:
    """
    Scans all students in the database and triggers automatic warnings
    for those with attendance < 75%.
    """
    students = Student.query.all()
    sent_count = 0
    skipped_count = 0
    results = []

    for student in students:
        if student.total_classes > 0 and student.attendance_percentage < 75.0:
            success, msg = send_low_attendance_email(student, force=False)
            if success:
                sent_count += 1
                results.append({"roll": student.roll_number, "name": student.full_name, "status": "sent", "msg": msg})
            else:
                skipped_count += 1
                results.append({"roll": student.roll_number, "name": student.full_name, "status": "skipped", "msg": msg})

    return {
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "total_checked": len(students),
        "results": results,
    }
