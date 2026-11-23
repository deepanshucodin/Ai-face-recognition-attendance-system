from datetime import datetime

from extensions import db


class FaceEncoding(db.Model):
    __tablename__ = "face_encodings"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    encoding = db.Column(db.LargeBinary, nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="encodings")
