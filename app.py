import logging
import sys
from pathlib import Path

from flask import Flask, render_template

# Ensure local packages directory is recognized on Windows only
if sys.platform == "win32":
    packages_path = Path(__file__).resolve().parent / "packages"
    if packages_path.exists() and str(packages_path) not in sys.path:
        sys.path.insert(0, str(packages_path))

from config import Config
from extensions import csrf, db
from models import Admin
from routes.attendance import attendance_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.reports import reports_bp
from routes.settings import settings_bp
from routes.student_portal import student_bp
from routes.students import students_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    for folder_key in ["UPLOAD_FOLDER", "PROCESSED_FOLDER", "REGISTERED_FACES_FOLDER", "EXPORT_FOLDER", "LOGS_FOLDER"]:
        Path(app.config[folder_key]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    configure_logging(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(student_bp)

    register_error_handlers(app)

    with app.app_context():
        try:
            db.create_all()
            seed_admin()
        except Exception as exc:
            app.logger.warning(f"Database setup note: {exc}")

    return app


def configure_logging(app):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_dir / "app.log")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def seed_admin():
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("layout/error.html", code=404, message="Page not found"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("layout/error.html", code=500, message="Something went wrong"), 500


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
