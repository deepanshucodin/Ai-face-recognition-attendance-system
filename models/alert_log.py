from datetime import datetime

from extensions import db


class AlertLog(db.Model):
    __tablename__ = "alert_logs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    recipient_email = db.Column(db.String(150), nullable=False)
    attendance_percentage = db.Column(db.Float, nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    message_snippet = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="SENT")  # SENT, SIMULATED, FAILED
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="alert_logs")
