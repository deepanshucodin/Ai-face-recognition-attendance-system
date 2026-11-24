import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "faceattend-secret-key-super-secure-production-ready")
    
    # Database URL with automatic fix for Render/Heroku postgres:// schema
    _db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'database.db'}")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Directories
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    PROCESSED_FOLDER = BASE_DIR / "static" / "processed"
    REGISTERED_FACES_FOLDER = BASE_DIR / "static" / "registered_faces"
    EXPORT_FOLDER = BASE_DIR / "exports"
    LOGS_FOLDER = BASE_DIR / "logs"

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # Face Detection & Accuracy Enhancement Parameters
    # COSINE_THRESHOLD: 0.363 standard SFace threshold for match
    COSINE_THRESHOLD = float(os.getenv("COSINE_THRESHOLD", "0.363"))
    FACE_TOLERANCE = float(os.getenv("FACE_TOLERANCE", "0.44"))
    FACE_DETECTION_MODEL = os.getenv("FACE_DETECTION_MODEL", "hog")  # "hog", "cnn", or "opencv_ensemble"
    FACE_UPSAMPLE_TIMES = int(os.getenv("FACE_UPSAMPLE_TIMES", "1"))  # 1 or 2 enables small face detection in classroom back rows
    ENHANCE_CONTRAST_CLAHE = os.getenv("ENHANCE_CONTRAST_CLAHE", "true").lower() == "true"
    ENABLE_FACE_ALIGNMENT = os.getenv("ENABLE_FACE_ALIGNMENT", "true").lower() == "true"
    ENABLE_PROFILE_DETECTION = os.getenv("ENABLE_PROFILE_DETECTION", "true").lower() == "true"

    # Attendance & Automatic Email Warning Parameters
    LOW_ATTENDANCE_THRESHOLD = float(os.getenv("LOW_ATTENDANCE_THRESHOLD", "75.0"))
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply-attendance@college.edu")
    MAIL_SENDER_NAME = os.getenv("MAIL_SENDER_NAME", "College Academic Department")
    MAIL_ALERT_ENABLED = os.getenv("MAIL_ALERT_ENABLED", "true").lower() == "true"

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
