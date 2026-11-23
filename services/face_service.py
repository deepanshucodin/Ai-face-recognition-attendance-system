import logging
import math
import pickle
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np
from flask import current_app

from extensions import db
from models import Attendance, FaceEncoding, Student
from services.email_service import send_low_attendance_email

logger = logging.getLogger("faceattend.face_service")


@dataclass
class RecognitionResult:
    recognized: list[dict]
    unknown_count: int
    processed_image: str | None
    summary: dict


# Model file locations
_WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "weights"
_YUNET_PATH = _WEIGHTS_DIR / "face_detection_yunet_2023mar.onnx"
_SFACE_PATH = _WEIGHTS_DIR / "face_recognition_sface_2021dec.onnx"

_SFACE_RECOGNIZER = None
_FRONTAL_CASCADE_ALT2 = None
_FRONTAL_CASCADE_DEFAULT = None
_PROFILE_CASCADE = None


def get_sface_recognizer():
    global _SFACE_RECOGNIZER
    if _SFACE_RECOGNIZER is None and _SFACE_PATH.exists():
        try:
            _SFACE_RECOGNIZER = cv2.FaceRecognizerSF.create(str(_SFACE_PATH), "")
            logger.info("Initialized OpenCV SFace Deep Face Recognizer")
        except Exception as exc:
            logger.warning(f"Failed to initialize SFace: {exc}")
    return _SFACE_RECOGNIZER


def get_yunet_detector(width: int, height: int, score_threshold: float = 0.45):
    if _YUNET_PATH.exists():
        try:
            return cv2.FaceDetectorYN.create(
                str(_YUNET_PATH),
                "",
                (int(width), int(height)),
                score_threshold=score_threshold,
                nms_threshold=0.3,
            )
        except Exception as exc:
            logger.warning(f"Failed to initialize YuNet: {exc}")
    return None


def _get_cascades():
    global _FRONTAL_CASCADE_ALT2, _FRONTAL_CASCADE_DEFAULT, _PROFILE_CASCADE
    if _FRONTAL_CASCADE_ALT2 is None:
        alt2_path = cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
        default_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        profile_path = cv2.data.haarcascades + "haarcascade_profileface.xml"

        _FRONTAL_CASCADE_ALT2 = cv2.CascadeClassifier(alt2_path)
        _FRONTAL_CASCADE_DEFAULT = cv2.CascadeClassifier(default_path)
        _PROFILE_CASCADE = cv2.CascadeClassifier(profile_path)
    return _FRONTAL_CASCADE_ALT2, _FRONTAL_CASCADE_DEFAULT, _PROFILE_CASCADE


def get_face_recognition_module():
    """Tries to import dlib/face_recognition. Returns module or None if not installed."""
    try:
        import face_recognition
        return face_recognition
    except (ImportError, Exception):
        return None


def preprocess_image_for_detection(rgb_image: np.ndarray, apply_clahe: bool = True, apply_denoise: bool = True) -> np.ndarray:
    """
    Applies multi-stage image preprocessing:
    1. LAB Color Space CLAHE for illumination normalization
    2. Dynamic Gamma Correction for dark classrooms
    3. Bilateral filter for noise reduction while preserving sharp facial edges
    """
    enhanced = rgb_image.copy()

    if apply_clahe:
        lab = cv2.cvtColor(enhanced, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.8, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge((l_clahe, a, b)), cv2.COLOR_LAB2RGB)

    gray = cv2.cvtColor(enhanced, cv2.COLOR_RGB2GRAY)
    mean_val = np.mean(gray)
    if mean_val < 85:
        gamma = 0.72
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, table)
    elif mean_val > 185:
        gamma = 1.25
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, table)

    if apply_denoise:
        enhanced = cv2.bilateralFilter(enhanced, d=5, sigmaColor=35, sigmaSpace=35)

    return enhanced


def compute_iou(box1: tuple, box2: tuple) -> float:
    t1, r1, b1, l1 = box1
    t2, r2, b2, l2 = box2
    inter_top = max(t1, t2)
    inter_left = max(l1, l2)
    inter_bottom = min(b1, b2)
    inter_right = min(r1, r2)
    if inter_right < inter_left or inter_bottom < inter_top:
        return 0.0
    inter_area = (inter_right - inter_left) * (inter_bottom - inter_top)
    area1 = (r1 - l1) * (b1 - t1)
    area2 = (r2 - l2) * (b2 - t2)
    union_area = area1 + area2 - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def non_maximum_suppression(boxes: list[tuple], iou_threshold: float = 0.35) -> list[tuple]:
    if not boxes:
        return []
    sorted_boxes = sorted(boxes, key=lambda b: (b[1] - b[3]) * (b[2] - b[0]), reverse=True)
    kept = []
    for box in sorted_boxes:
        overlap = any(compute_iou(box, k) > iou_threshold for k in kept)
        if not overlap:
            kept.append(box)
    return kept


def detect_faces_yunet(bgr_image: np.ndarray, score_threshold: float = 0.45) -> list:
    """Detects faces using YuNet DNN. Returns list of 15-element detections."""
    h, w, _ = bgr_image.shape
    detector = get_yunet_detector(w, h, score_threshold=score_threshold)
    if detector is None:
        return []
    detector.setInputSize((int(w), int(h)))
    _, faces = detector.detect(bgr_image)
    if faces is None or len(faces) == 0:
        return []
    return list(faces)


def face_to_box(face: np.ndarray, img_shape: tuple) -> tuple[int, int, int, int]:
    """Converts YuNet face detection array to (top, right, bottom, left)."""
    h, w = img_shape[:2]
    x, y, fw, fh = face[:4]
    top = int(max(0, y))
    left = int(max(0, x))
    bottom = int(min(h, y + fh))
    right = int(min(w, x + fw))
    return (top, right, bottom, left)


def box_to_face(box: tuple, score: float = 0.9) -> np.ndarray:
    """Converts (top, right, bottom, left) to synthetic YuNet 15-element array with approximate landmarks."""
    top, right, bottom, left = box
    w = max(1, right - left)
    h = max(1, bottom - top)
    x = left
    y = top
    return np.array(
        [
            x, y, w, h,
            x + 0.35 * w, y + 0.38 * h,  # right eye
            x + 0.65 * w, y + 0.38 * h,  # left eye
            x + 0.50 * w, y + 0.55 * h,  # nose
            x + 0.40 * w, y + 0.75 * h,  # right mouth corner
            x + 0.60 * w, y + 0.75 * h,  # left mouth corner
            score,
        ],
        dtype=np.float32,
    )


def extract_sface_feature(bgr_image: np.ndarray, face: np.ndarray) -> Optional[np.ndarray]:
    """Extracts 128D SFace feature vector from aligned face crop."""
    recognizer = get_sface_recognizer()
    if recognizer is None:
        return None
    try:
        aligned = recognizer.alignCrop(bgr_image, face)
        feat = recognizer.feature(aligned)[0]
        return feat.astype(np.float32)
    except Exception as exc:
        logger.warning(f"SFace feature extraction failed: {exc}")
        return None


def detect_faces_opencv_ensemble(rgb_image: np.ndarray) -> list[tuple[int, int, int, int]]:
    alt2, default, profile = _get_cascades()
    gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray)
    boxes = []

    faces_alt2 = alt2.detectMultiScale(gray_clahe, scaleFactor=1.06, minNeighbors=4, minSize=(28, 28))
    for (x, y, w, h) in faces_alt2:
        boxes.append((int(y), int(x + w), int(y + h), int(x)))

    faces_def = default.detectMultiScale(gray_clahe, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    for (x, y, w, h) in faces_def:
        boxes.append((int(y), int(x + w), int(y + h), int(x)))

    profiles = profile.detectMultiScale(gray_clahe, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
    for (x, y, w, h) in profiles:
        boxes.append((int(y), int(x + w), int(y + h), int(x)))

    gray_flipped = cv2.flip(gray_clahe, 1)
    profiles_flipped = profile.detectMultiScale(gray_flipped, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
    width = gray.shape[1]
    for (x, y, w, h) in profiles_flipped:
        orig_x = width - (x + w)
        boxes.append((int(y), int(orig_x + w), int(y + h), int(orig_x)))

    return non_maximum_suppression(boxes, iou_threshold=0.35)


def detect_face_locations(rgb_image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detects all face bounding boxes (top, right, bottom, left) using YuNet, dlib, or Haar cascade."""
    bgr = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    h, w, _ = bgr.shape

    # 1. Primary: YuNet DNN
    faces = detect_faces_yunet(bgr, score_threshold=0.45)
    if faces:
        return [face_to_box(f, (h, w)) for f in faces]

    # 2. Secondary: face_recognition (dlib) if installed
    face_rec = get_face_recognition_module()
    if face_rec is not None:
        try:
            boxes = face_rec.face_locations(rgb_image)
            if boxes:
                return list(boxes)
        except Exception:
            pass

    # 3. Fallback: Haar Cascade Ensemble
    return detect_faces_opencv_ensemble(rgb_image)


def _extract_fallback_descriptor(rgb_image: np.ndarray, box: tuple) -> np.ndarray:
    top, right, bottom, left = box
    h, w, _ = rgb_image.shape
    t = max(0, top)
    b = min(h, bottom)
    l = max(0, left)
    r = min(w, right)
    crop = rgb_image[t:b, l:r]
    if crop.size == 0:
        return np.zeros(128, dtype=np.float32)

    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    norm_face = clahe.apply(resized)

    features = []
    cell_h, cell_w = 16, 16
    for i in range(4):
        for j in range(4):
            cell = norm_face[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
            hist, _ = np.histogram(cell, bins=8, range=(0, 256), density=True)
            features.extend(hist)

    feat_vec = np.array(features, dtype=np.float32)
    norm = np.linalg.norm(feat_vec)
    if norm > 0:
        feat_vec /= norm
    return feat_vec


def create_encoding_from_image(path: Path) -> np.ndarray:
    """Extracts high-precision facial encoding for student registration."""
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise ValueError(f"Could not read image from {path}")
    h, w, _ = bgr.shape

    recognizer = get_sface_recognizer()

    # 1. Try YuNet face detection
    faces = detect_faces_yunet(bgr, score_threshold=0.45)
    if recognizer is not None and len(faces) == 1:
        feat = extract_sface_feature(bgr, faces[0])
        if feat is not None:
            return feat

    # 2. General location detection
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    locations = detect_face_locations(rgb)

    if len(locations) != 1:
        if len(locations) == 0:
            raise ValueError("No face detected. Please upload a clear, well-lit photo looking towards the camera.")
        raise ValueError(f"Found {len(locations)} faces in the image. Registration requires exactly one face.")

    if recognizer is not None:
        dummy_face = box_to_face(locations[0])
        feat = extract_sface_feature(bgr, dummy_face)
        if feat is not None:
            return feat

    face_rec = get_face_recognition_module()
    if face_rec is not None:
        try:
            encodings = face_rec.face_encodings(rgb, known_face_locations=locations)
            if encodings:
                return encodings[0]
        except Exception:
            pass

    return _extract_fallback_descriptor(rgb, locations[0])


def serialize_encoding(encoding: np.ndarray) -> bytes:
    return pickle.dumps(encoding, protocol=pickle.HIGHEST_PROTOCOL)


def deserialize_encoding(blob: bytes) -> np.ndarray:
    return pickle.loads(blob)


def _load_rgb_image(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise ValueError(f"Could not read image from {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def get_known_faces() -> tuple[list[np.ndarray], list[Student]]:
    rows = (
        db.session.query(FaceEncoding, Student)
        .join(Student, FaceEncoding.student_id == Student.id)
        .order_by(Student.roll_number.asc())
        .all()
    )
    encodings = [deserialize_encoding(row.FaceEncoding.encoding) for row in rows]
    students = [row.Student for row in rows]
    return encodings, students


def compute_cosine_similarity(feat1: np.ndarray, feat2: np.ndarray) -> float:
    norm1 = np.linalg.norm(feat1)
    norm2 = np.linalg.norm(feat2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(feat1, feat2) / (norm1 * norm2))


def calculate_calibrated_confidence(score: float, threshold: float = 0.363) -> float:
    """
    Calibrated statistical confidence formula:
    Cosine >= 0.363 matches student:
    Score 0.363 -> 75.0%
    Score 0.500 -> 84.6%
    Score 0.680 -> 97.2%
    Score 0.720 -> 99.5%
    """
    if score is None or score <= 0.0:
        return 0.0
    if score >= threshold:
        conf = 75.0 + (score - threshold) * 70.0
        return round(float(np.clip(conf, 75.0, 99.9)), 1)
    else:
        conf = (score / max(threshold, 0.01)) * 70.0
        return round(float(np.clip(conf, 5.0, 74.0)), 1)


def _best_student_for_face(face_encoding: np.ndarray, known_encodings: list[np.ndarray], known_students: list[Student], threshold: float = 0.363):
    if not known_encodings or not known_students:
        return None, 0.0

    try:
        known_mat = np.array(known_encodings)
        norms_k = np.linalg.norm(known_mat, axis=1)
        norm_q = np.linalg.norm(face_encoding)
        if norm_q == 0 or np.any(norms_k == 0):
            scores = [compute_cosine_similarity(face_encoding, k) for k in known_encodings]
        else:
            scores = np.dot(known_mat, face_encoding) / (norms_k * norm_q)
    except Exception:
        scores = [compute_cosine_similarity(face_encoding, k) for k in known_encodings]

    scores = np.array(scores)
    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])

    if best_score >= threshold:
        return known_students[best_index], best_score
    return None, best_score


def mark_absent_for_missing_students(present_student_ids: Iterable[int], attendance_date, method: str) -> int:
    """
    Marks attendance records:
    - For all methods, recognized students are marked PRESENT (or updated from ABSENT to PRESENT).
    - For bulk classroom uploads ('upload'), absent students are recorded as ABSENT.
    - For individual webcam check-ins ('webcam'), only recognized attendees are recorded without falsely penalizing the rest of the class.
    """
    present_ids = set(present_student_ids)
    created = 0
    for student in Student.query.all():
        existing = Attendance.query.filter_by(student_id=student.id, date=attendance_date).first()
        if existing:
            if student.id in present_ids and existing.status != "PRESENT":
                existing.status = "PRESENT"
                existing.method = method
            continue

        if method == "upload":
            status = "PRESENT" if student.id in present_ids else "ABSENT"
            db.session.add(Attendance(student_id=student.id, date=attendance_date, status=status, method=method))
            created += 1
        elif student.id in present_ids:
            db.session.add(Attendance(student_id=student.id, date=attendance_date, status="PRESENT", method=method))
            created += 1
    return created


def recognize_image(image_path: Path, attendance_date, method: str = "upload") -> RecognitionResult:
    """
    High-Accuracy Deep Neural Network Face Recognition & Attendance Pipeline:
    1. Detects faces via YuNet DNN (or multi-scale ensemble fallback)
    2. Aligns faces and extracts deep 128D SFace feature embeddings
    3. Matches with calibrated cosine similarity scoring
    4. Records attendance in database
    5. Dispatches low attendance warning alerts (< 75%)
    6. Produces annotated bounding box image
    """
    known_encodings, known_students = get_known_faces()
    bgr_image = cv2.imread(str(image_path))
    if bgr_image is None:
        raise ValueError(f"Could not load image: {image_path}")

    h, w, _ = bgr_image.shape
    recognizer = get_sface_recognizer()

    # 1. Detect faces using YuNet DNN
    yunet_faces = detect_faces_yunet(bgr_image, score_threshold=0.45)
    locations = []
    encodings = []

    if yunet_faces and recognizer is not None:
        for yface in yunet_faces:
            box = face_to_box(yface, (h, w))
            feat = extract_sface_feature(bgr_image, yface)
            if feat is not None:
                locations.append(box)
                encodings.append(feat)

    # If YuNet found no faces, fallback to cascade ensemble
    if len(locations) == 0:
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        cascade_boxes = detect_face_locations(rgb_image)
        for box in cascade_boxes:
            dummy_face = box_to_face(box)
            feat = extract_sface_feature(bgr_image, dummy_face) if recognizer is not None else None
            if feat is None:
                feat = _extract_fallback_descriptor(rgb_image, box)
            locations.append(box)
            encodings.append(feat)

    threshold = current_app.config.get("COSINE_THRESHOLD", 0.363)
    present_ids: set[int] = set()
    recognized: list[dict] = []
    unknown_count = 0

    display_image = bgr_image.copy()

    for (top, right, bottom, left), encoding in zip(locations, encodings):
        student, score = _best_student_for_face(encoding, known_encodings, known_students, threshold)
        confidence = calculate_calibrated_confidence(score, threshold)

        if student and student.id not in present_ids:
            present_ids.add(student.id)
            recognized.append(
                {
                    "id": student.id,
                    "name": student.full_name,
                    "roll_number": student.roll_number,
                    "confidence": confidence,
                    "attendance_pct": student.attendance_percentage,
                }
            )
            label = f"{student.full_name} ({student.roll_number}) - {confidence}%"
            box_color = (46, 204, 113)  # Bright Green
            header_color = (39, 174, 96)
        elif student:
            label = f"{student.full_name} (Duplicate)"
            box_color = (241, 196, 15)  # Amber / Yellow
            header_color = (212, 172, 13)
        else:
            unknown_count += 1
            label = f"Unknown ({confidence}%)"
            box_color = (231, 76, 60)  # Red
            header_color = (192, 57, 43)

        # Draw polished aesthetic bounding boxes
        cv2.rectangle(display_image, (left, top), (right, bottom), box_color, 2)
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        header_top = max(0, top - text_h - 10)
        cv2.rectangle(display_image, (left, header_top), (min(display_image.shape[1], left + text_w + 12), top), header_color, cv2.FILLED)
        cv2.putText(display_image, label, (left + 6, top - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # Record attendance
    mark_absent_for_missing_students(present_ids, attendance_date, method)
    db.session.commit()

    # Automated feature: Low attendance warning alerts
    alerts_triggered = 0
    all_students = Student.query.all()
    for student in all_students:
        if student.total_classes > 0 and student.attendance_percentage < 75.0:
            success, msg = send_low_attendance_email(student, force=False)
            if success:
                alerts_triggered += 1
                logger.info(f"Automated warning email sent to {student.roll_number}: {msg}")

    # Save processed annotated image
    processed_name = f"processed_{uuid.uuid4().hex}.jpg"
    processed_path = Path(current_app.config["PROCESSED_FOLDER"]) / processed_name
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(processed_path), display_image)

    total_students = len(all_students)
    summary = {
        "faces_detected": len(locations),
        "recognized_count": len(present_ids),
        "unknown_count": unknown_count,
        "absent_count": max(total_students - len(present_ids), 0) if method == "upload" else 0,
        "alerts_triggered": alerts_triggered,
    }
    return RecognitionResult(recognized, unknown_count, f"processed/{processed_name}", summary)
