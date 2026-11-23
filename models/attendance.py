from datetime import date, datetime, time

from extensions import db


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    time = db.Column(db.Time, default=lambda: datetime.now().time().replace(microsecond=0), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ABSENT", index=True)
    method = db.Column(db.String(40), nullable=False, default="manual")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="attendance_records")

    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="uq_student_attendance_date"),
    )
