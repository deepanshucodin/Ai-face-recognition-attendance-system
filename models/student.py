from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(140), nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    department = db.Column(db.String(120), nullable=False)
    year_semester = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(150), nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    image_folder = db.Column(db.String(255), nullable=True)
    last_alert_sent = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    encodings = db.relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    attendance_records = db.relationship("Attendance", back_populates="student", cascade="all, delete-orphan", order_by="desc(Attendance.date)")
    alert_logs = db.relationship("AlertLog", back_populates="student", cascade="all, delete-orphan", order_by="desc(AlertLog.sent_at)")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            # Default to roll number if password not set
            return password.strip().upper() == self.roll_number.strip().upper()
        return check_password_hash(self.password_hash, password)

    @property
    def total_classes(self) -> int:
        return len(self.attendance_records)

    @property
    def present_count(self) -> int:
        return len([record for record in self.attendance_records if record.status == "PRESENT"])

    @property
    def absent_count(self) -> int:
        return len([record for record in self.attendance_records if record.status == "ABSENT"])

    @property
    def attendance_percentage(self) -> float:
        total = self.total_classes
        if total == 0:
            return 100.0  # New students start with 100% until classes are recorded
        present = self.present_count
        return round((present / total) * 100, 2)

    @property
    def is_low_attendance(self) -> bool:
        if self.total_classes == 0:
            return False
        return self.attendance_percentage < 75.0

    @property
    def attendance_status_badge(self) -> str:
        if self.total_classes == 0:
            return "info"
        if self.attendance_percentage >= 75.0:
            return "success"
        if self.attendance_percentage >= 65.0:
            return "warning"
        return "danger"
