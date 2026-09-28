import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("AI_API_KEY", "")  # tests never call a real AI

from app.core.auth import CurrentUser, get_current_user  # noqa: E402
from app.core.ratelimit import RateLimiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models.schemas import AIOpinion  # noqa: E402
from app.routers import observations as obs_router  # noqa: E402
from app.services.db import get_repo  # noqa: E402
from app.services.storage import get_storage  # noqa: E402
from tests.fakes import FakeRepo, FakeStorage  # noqa: E402

USER_A = CurrentUser(id="user-a", email="a@test.com")
USER_B = CurrentUser(id="user-b", email="b@test.com")


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def as_user(repo, storage, monkeypatch):
    """as_user(USER_A) -> TestClient authenticated as that user, sharing one fake DB."""

    async def fake_opinion(image_bytes, ind, settings=None):
        return AIOpinion(
            suggested_score=3,
            confidence=0.8,
            visible_evidence=["brown water"],
            reason="Water looks cloudy",
            can_assess=True,
        )

    def fake_quality(jpeg, previous_hashes):
        return {
            "blur_score": 500.0,
            "brightness": 128.0,
            "phash": "0" * 16,
            "is_blurry": False,
            "is_dark": False,
            "is_overexposed": False,
            "is_duplicate": False,
            "score": 1.0,
        }

    monkeypatch.setattr(obs_router.ai_opinion, "get_opinion", fake_opinion)
    monkeypatch.setattr(obs_router.pq, "check_quality", fake_quality)
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[obs_router.get_ai_limiter] = lambda: RateLimiter(1000)

    def _make(user: CurrentUser) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


def jpeg_bytes(color=(90, 120, 140), size=(64, 64), exif: bool = False) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretPhoneMaker"  # Make
        img.save(buf, format="JPEG", exif=ex.tobytes())
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()
