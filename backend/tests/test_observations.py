import io

from PIL import Image

from app.services.indicators import load_indicators
from app.services.storage import process_image
from tests.conftest import USER_A, USER_B, jpeg_bytes

REQUIRED = [i.id for i in load_indicators() if i.required]


def _answer(client, obs_id, ind_id, score=2):
    return client.post(
        f"/api/v1/observations/{obs_id}/indicators/{ind_id}",
        data={"human_score": str(score)},
        files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
    )


def test_health(as_user):
    r = as_user(USER_A).get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_missing_token_gives_401_in_error_format():
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/api/v1/observations/mine")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_full_v1_flow(as_user, storage):
    c = as_user(USER_A)
    obs = c.post("/api/v1/observations", json={"lat": 28.6, "lng": 77.4}).json()
    assert obs["status"] == "draft"

    for ind in REQUIRED:
        r = _answer(c, obs["id"], ind)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ai_score"] == 3 and body["can_assess"] is True

    # user accepts AI's answer for the first indicator
    r = c.patch(f"/api/v1/observations/{obs['id']}/indicators/{REQUIRED[0]}", json={"used_ai_answer": True})
    assert r.status_code == 200 and r.json()["final_score"] == 3

    r = c.post(f"/api/v1/observations/{obs['id']}/submit")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"

    detail = c.get(f"/api/v1/observations/{obs['id']}").json()
    assert len(detail["answers"]) == len(REQUIRED)
    assert detail["answers"][0]["photo_url"].startswith("https://signed.example/user-a/")

    page = c.get("/api/v1/observations/mine?offset=0&limit=10").json()
    assert page["total"] == 1

    # submitted observation is locked
    assert _answer(c, obs["id"], REQUIRED[0]).status_code == 409


def test_other_users_observation_is_404(as_user):
    obs = as_user(USER_A).post("/api/v1/observations", json={}).json()
    b = as_user(USER_B)
    r = b.get(f"/api/v1/observations/{obs['id']}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert _answer(b, obs["id"], REQUIRED[0]).status_code == 404


def test_retake_upserts_instead_of_duplicating(as_user, repo):
    c = as_user(USER_A)
    obs = c.post("/api/v1/observations", json={}).json()
    _answer(c, obs["id"], REQUIRED[0], score=1)
    _answer(c, obs["id"], REQUIRED[0], score=4)
    answers = repo.list_answers(obs["id"])
    assert len(answers) == 1 and answers[0]["human_score"] == 4


def test_submit_with_missing_indicators_fails(as_user):
    c = as_user(USER_A)
    obs = c.post("/api/v1/observations", json={}).json()
    _answer(c, obs["id"], REQUIRED[0])
    r = c.post(f"/api/v1/observations/{obs['id']}/submit")
    assert r.status_code == 422 and r.json()["error"]["code"] == "MISSING_INDICATORS"


def test_score_out_of_scale_rejected(as_user):
    c = as_user(USER_A)
    obs = c.post("/api/v1/observations", json={}).json()
    assert _answer(c, obs["id"], REQUIRED[0], score=7).status_code == 422


def test_non_image_upload_rejected(as_user):
    c = as_user(USER_A)
    obs = c.post("/api/v1/observations", json={}).json()
    r = c.post(
        f"/api/v1/observations/{obs['id']}/indicators/{REQUIRED[0]}",
        data={"human_score": "2"},
        files={"photo": ("evil.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 415


def test_image_is_reencoded_resized_and_exif_stripped():
    raw = jpeg_bytes(size=(3000, 2000), exif=True)
    out = process_image(raw, "image/jpeg", 8)
    img = Image.open(io.BytesIO(out))
    assert max(img.size) == 1280
    assert not img.getexif()
