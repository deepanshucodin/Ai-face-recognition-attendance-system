import smtplib
from email.mime.text import MIMEText

from flask import Blueprint, current_app, flash, render_template, request

from extensions import db
from models import Admin
from utils.auth import login_required

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action", "general")

        if action == "face_settings":
            tolerance = request.form.get("face_tolerance", "").strip()
            upsample = request.form.get("face_upsample_times", "").strip()
            clahe = request.form.get("enhance_contrast_clahe") == "on"

            if tolerance:
                try:
                    val = float(tolerance)
                    if 0.30 <= val <= 0.65:
                        current_app.config["FACE_TOLERANCE"] = val
                        flash(f"Face tolerance set to {val}.", "success")
                except ValueError:
                    flash("Invalid tolerance value.", "danger")

            if upsample:
                try:
                    u_val = int(upsample)
                    if 0 <= u_val <= 2:
                        current_app.config["FACE_UPSAMPLE_TIMES"] = u_val
                        flash(f"Upsampling factor updated to {u_val}x.", "success")
                except ValueError:
                    pass

            current_app.config["ENHANCE_CONTRAST_CLAHE"] = clahe
            flash("Face detection parameters updated.", "success")

        elif action == "mail_settings":
            current_app.config["MAIL_SERVER"] = request.form.get("mail_server", "").strip()
            current_app.config["MAIL_PORT"] = int(request.form.get("mail_port", 587) or 587)
            current_app.config["MAIL_USERNAME"] = request.form.get("mail_username", "").strip()
            if request.form.get("mail_password"):
                current_app.config["MAIL_PASSWORD"] = request.form.get("mail_password").strip()
            current_app.config["MAIL_DEFAULT_SENDER"] = request.form.get("mail_default_sender", "").strip()
            flash("Email SMTP settings updated for running application.", "success")

        elif action == "test_email":
            target_email = request.form.get("test_email_target", "").strip()
            if not target_email or "@" not in target_email:
                flash("Enter a valid test email address.", "danger")
            else:
                user = current_app.config.get("MAIL_USERNAME")
                pwd = current_app.config.get("MAIL_PASSWORD")
                server = current_app.config.get("MAIL_SERVER")
                port = current_app.config.get("MAIL_PORT")
                sender = current_app.config.get("MAIL_DEFAULT_SENDER") or user

                if user and pwd:
                    try:
                        msg = MIMEText("This is a test notification from FaceAttend Attendance System.")
                        msg["Subject"] = "FaceAttend - Test Email Notification"
                        msg["From"] = sender
                        msg["To"] = target_email

                        with smtplib.SMTP(server, port, timeout=10) as s:
                            if current_app.config.get("MAIL_USE_TLS", True):
                                s.starttls()
                            s.login(user, pwd)
                            s.sendmail(sender, [target_email], msg.as_string())
                        flash(f"Test email successfully dispatched to {target_email}!", "success")
                    except Exception as exc:
                        flash(f"SMTP Test Error: {exc}", "danger")
                else:
                    flash(f"SMTP credentials not entered. Test simulated for {target_email} (check logs/email_alerts.log).", "info")

        elif action == "create_admin":
            new_username = request.form.get("new_username", "").strip()
            new_password = request.form.get("new_password", "").strip()
            if new_username and new_password:
                if Admin.query.filter_by(username=new_username).first():
                    flash("Admin username already exists.", "warning")
                else:
                    admin = Admin(username=new_username)
                    admin.set_password(new_password)
                    db.session.add(admin)
                    db.session.commit()
                    flash(f"New admin account '{new_username}' created.", "success")

    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return render_template("dashboard/settings.html", admins=admins, config=current_app.config)
