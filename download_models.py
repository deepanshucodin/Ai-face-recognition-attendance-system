"""
Helper script to download OpenCV Deep Learning models:
- YuNet (Face Detector)
- SFace (Deep Face Recognizer)
"""
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WEIGHTS_DIR = BASE_DIR / "weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

MODELS = {
    "face_detection_yunet_2023mar.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def download_models():
    for filename, url in MODELS.items():
        dest = WEIGHTS_DIR / filename
        if not dest.exists() or dest.stat().st_size == 0:
            print(f"Downloading {filename}...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            print(f"Downloaded {filename} ({dest.stat().st_size} bytes)")
        else:
            print(f"Model already present: {filename} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    download_models()
