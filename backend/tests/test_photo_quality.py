import cv2
import numpy as np

from app.services.photo_quality import check_quality


def _jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _checkerboard(size=256, square=16) -> np.ndarray:
    img = np.zeros((size, size), dtype=np.uint8)
    for y in range(0, size, square):
        for x in range(0, size, square):
            if ((x // square) + (y // square)) % 2 == 0:
                img[y : y + square, x : x + square] = 255
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_sharp_image_is_not_blurry():
    q = check_quality(_jpeg(_checkerboard()), [])
    assert q["is_blurry"] is False


def test_blurred_image_is_blurry():
    blurred = cv2.GaussianBlur(_checkerboard(), (25, 25), 0)
    q = check_quality(_jpeg(blurred), [])
    assert q["is_blurry"] is True


def test_black_image_is_dark():
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    q = check_quality(_jpeg(img), [])
    assert q["is_dark"] is True


def test_white_image_is_overexposed():
    img = np.full((64, 64, 3), 255, dtype=np.uint8)
    q = check_quality(_jpeg(img), [])
    assert q["is_overexposed"] is True


def test_own_hash_in_previous_is_duplicate():
    jpeg = _jpeg(_checkerboard())
    first = check_quality(jpeg, [])
    q = check_quality(jpeg, [first["phash"]])
    assert q["is_duplicate"] is True
    assert q["score"] == 0
