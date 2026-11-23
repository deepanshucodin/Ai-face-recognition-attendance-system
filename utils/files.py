import re
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def safe_student_folder(name: str, roll_number: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{roll_number}_{name}").strip("_")
    return slug[:90] or str(uuid.uuid4())


def unique_filename(filename: str) -> str:
    safe_name = secure_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    stem = Path(safe_name).stem[:50] or "image"
    return f"{stem}_{uuid.uuid4().hex[:10]}{suffix}"
