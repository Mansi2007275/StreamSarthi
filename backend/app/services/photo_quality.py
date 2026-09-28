"""Photo quality checks: blur, brightness, duplicate detection.

Runs on every photo upload (see routers/observations.py). CPU-bound, so callers
should run check_quality() through starlette.concurrency.run_in_threadpool.
A failure here must never block saving the observation.
"""

import io

import cv2
import imagehash
import numpy as np
from PIL import Image

BLUR_THRESHOLD = 100
DARK_THRESHOLD = 40
BRIGHT_THRESHOLD = 220
DUPLICATE_DISTANCE = 5


def _hamming(phash: imagehash.ImageHash, other: str) -> int:
    try:
        return phash - imagehash.hex_to_hash(other)
    except ValueError:
        return 999


def check_quality(jpeg: bytes, previous_hashes: list[str]) -> dict:
    gray = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    phash = imagehash.phash(Image.open(io.BytesIO(jpeg)))

    q = {
        "blur_score": round(blur_score, 2),
        "brightness": round(brightness, 2),
        "phash": str(phash),
        "is_blurry": blur_score < BLUR_THRESHOLD,
        "is_dark": brightness < DARK_THRESHOLD,
        "is_overexposed": brightness > BRIGHT_THRESHOLD,
        "is_duplicate": any(_hamming(phash, h) <= DUPLICATE_DISTANCE for h in previous_hashes),
    }
    q["score"] = quality_score(q)
    return q


def quality_score(q: dict) -> float:
    if q["is_duplicate"]:
        return 0.0
    score = 1.0
    if q["is_blurry"]:
        score -= 0.4
    if q["is_dark"] or q["is_overexposed"]:
        score -= 0.3
    return max(score, 0.0)


def quality_flags(q: dict) -> list[str]:
    flags = []
    if q["is_blurry"]:
        flags.append("blurry_photo")
    if q["is_dark"]:
        flags.append("dark_photo")
    if q["is_overexposed"]:
        flags.append("overexposed_photo")
    if q["is_duplicate"]:
        flags.append("duplicate_photo")
    return flags
