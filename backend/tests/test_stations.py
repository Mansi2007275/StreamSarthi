"""Stream Stations: the public page, the source tag, and the Station Keeper badge."""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.ratelimit import RateLimiter
from app.main import app
from app.routers import stations as stations_router
from app.services import site_history
from app.services.db import get_repo
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from app.services.storage import get_storage
from tests.conftest import USER_A, USER_B, jpeg_bytes

CFG = load_game_config()
INTERVAL = CFG["adopted_check_interval_days"]
REQUIRED = [i.id for i in load_indicators() if i.required]


@pytest.fixture(autouse=True)
def generous_limiter():
    """The real limiter is an lru_cache singleton; tests must not share its counter."""
    limiter = RateLimiter(10_000)
    app.dependency_overrides[stations_router.get_station_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(stations_router.get_station_limiter, None)


@pytest.fixture
def public(repo, storage):
    """A client with no Authorization header at all - a passer-by with a phone."""
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.pop(get_repo, None)
    app.dependency_overrides.pop(get_storage, None)


def site(repo, name="Hindon Ghat", lat=28.669212345, lng=77.453787654):
    return repo.create_site(lat, lng, name)


def check_at(repo, as_user, user, site_id, submitted_at=None, source="app", one_health=None):
    client = as_user(user)
    obs_id = client.post(
        "/api/v1/observations",
        json={"lat": 28.6692, "lng": 77.4538, "site_id": site_id, "source": source},
    ).json()["id"]
    for ind in REQUIRED:
        client.post(
            f"/api/v1/observations/{obs_id}/indicators/{ind}",
            data={"human_score": "3", "human_confidence": "sure"},
            files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
        )
    client.post(f"/api/v1/observations/{obs_id}/submit")
    fields = {}
    if submitted_at:
        fields["submitted_at"] = submitted_at
    if one_health is not None:
        fields["one_health"] = one_health
    if fields:
        repo.update_observation(obs_id, fields)
    return obs_id


# ---------------- the public page ----------------


def test_a_passer_by_can_read_a_station_without_logging_in(public, repo):
    s = site(repo)
    r = public.get(f"/api/v1/stations/{s['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Hindon Ghat"
    assert body["station_number"] == s["station_number"]


def test_an_unchecked_station_is_waiting(public, repo):
    s = site(repo)
    body = public.get(f"/api/v1/stations/{s['id']}").json()
    assert body["waiting_for_check"] is True
    assert body["last_check"] is None
    assert body["days_since_check"] is None
    assert body["total_checks"] == 0
    assert body["headline"] is None
    assert body["recent_months"] == []


def test_a_recently_checked_station_is_not_waiting(public, repo, as_user):
    s = site(repo)
    check_at(repo, as_user, USER_A, s["id"])
    body = public.get(f"/api/v1/stations/{s['id']}").json()
    assert body["waiting_for_check"] is False
    assert body["total_checks"] == 1
    assert body["days_since_check"] == 0


def test_a_long_neglected_station_goes_back_to_waiting(public, repo, as_user):
    from datetime import timedelta

    from app.services import adoption

    s = site(repo)
    old = (adoption.today_utc() - timedelta(days=INTERVAL + 5)).isoformat() + "T09:00:00+00:00"
    check_at(repo, as_user, USER_A, s["id"], submitted_at=old)
    body = public.get(f"/api/v1/stations/{s['id']}").json()
    assert body["waiting_for_check"] is True
    assert body["days_since_check"] >= INTERVAL


def test_the_public_page_rounds_the_coordinates(public, repo):
    s = site(repo, lat=28.669212345, lng=77.453787654)
    body = public.get(f"/api/v1/stations/{s['id']}").json()
    assert body["lat"] == 28.669  # ~100 m, never a doorstep
    assert body["lng"] == 77.454


def test_the_public_page_leaks_nothing_about_any_person(public, repo, as_user):
    s = site(repo)
    repo.ensure_profile(USER_B.id, "private-person@example.test")
    repo.update_profile(USER_B.id, {"display_name": "private-person"})
    check_at(repo, as_user, USER_B, s["id"])

    raw = json.dumps(public.get(f"/api/v1/stations/{s['id']}").json())
    for leak in ("user_id", "voter_id", "email", "display_name", "photo", "private-person", USER_B.id):
        assert leak not in raw, f"the station page leaked {leak}"
    # and nothing that could be a per-person score either
    for leak in ("human_score", "ai_score", "expert_score", "trust_score", "crowd_score"):
        assert leak not in raw


def test_the_public_page_has_exactly_the_expected_fields(public, repo):
    s = site(repo)
    body = public.get(f"/api/v1/stations/{s['id']}").json()
    assert set(body.keys()) == {
        "site_id",
        "station_number",
        "name",
        "lat",
        "lng",
        "last_check",
        "days_since_check",
        "total_checks",
        "waiting_for_check",
        "one_health_level",
        "headline",
        "recent_months",
    }


def test_the_station_shows_the_last_six_months_oldest_first(public, repo, as_user):
    s = site(repo)
    for month in ("05", "06", "07"):
        check_at(
            repo,
            as_user,
            USER_A,
            s["id"],
            submitted_at=f"2026-{month}-10T09:00:00+00:00",
            one_health={"level": "poor", "drivers": []},
        )
    months = [d["month"] for d in public.get(f"/api/v1/stations/{s['id']}").json()["recent_months"]]
    assert months == ["2026-05", "2026-06", "2026-07"]


def test_the_station_headline_names_what_stood_out(public, repo, as_user):
    s = site(repo)
    check_at(
        repo,
        as_user,
        USER_A,
        s["id"],
        submitted_at="2026-10-01T09:00:00+00:00",
        one_health={"level": "poor", "drivers": [{"indicator_id": "water_colour", "label": "Water colour"}]},
    )
    body = public.get(f"/api/v1/stations/{s['id']}").json()
    assert body["one_health_level"] == "poor"
    assert "water colour" in body["headline"].lower()
    assert "poor" in body["headline"]


def test_an_unknown_station_is_404(public):
    assert public.get("/api/v1/stations/00000000-0000-0000-0000-000000000000").status_code == 404


def test_the_public_page_is_rate_limited(public, repo):
    limiter = RateLimiter(2, 60, "slow down")
    app.dependency_overrides[stations_router.get_station_limiter] = lambda: limiter
    s = site(repo)
    assert public.get(f"/api/v1/stations/{s['id']}").status_code == 200
    assert public.get(f"/api/v1/stations/{s['id']}").status_code == 200
    r = public.get(f"/api/v1/stations/{s['id']}")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


# ---------------- the headline, as a pure function ----------------


def entry(month, level, drivers=()):
    return {
        "month": month,
        "date": f"{month}-10",
        "one_health_level": level,
        "worst_indicators": list(drivers),
        "verified": True,
        "checks": 1,
        "mine": 0,
    }


def test_no_headline_without_a_reading():
    assert site_history.headline([]) is None
    assert site_history.headline([entry("2026-10", None)]) is None


def test_a_headline_without_drivers_still_says_the_level():
    assert "moderate" in site_history.headline([entry("2026-10", "moderate")])


def test_a_headline_lists_at_most_two_drivers():
    entries = [entry("2026-10", "poor", ["Water colour", "Litter and debris", "Water flow"])]
    text = site_history.headline(entries)
    assert "water colour" in text.lower()
    assert "litter and debris" in text.lower()
    assert "water flow" not in text.lower()


def test_a_headline_does_not_repeat_a_driver_across_months():
    entries = [entry("2026-10", "poor", ["Water colour"]), entry("2026-09", "poor", ["Water colour"])]
    text = site_history.headline(entries, months=2)
    assert text.lower().count("water colour") == 1
    assert "last 2 checks" in text


def test_recent_levels_are_capped_and_reversed():
    entries = [entry(f"2026-{m:02d}", "good") for m in range(12, 0, -1)]
    dots = site_history.recent_levels(entries, 6)
    assert len(dots) == 6
    assert dots[0]["month"] < dots[-1]["month"]  # oldest first


# ---------------- the source tag ----------------


def test_a_check_started_at_a_station_is_tagged(as_user, repo):
    s = site(repo)
    obs_id = check_at(repo, as_user, USER_A, s["id"], source="station")
    assert repo.get_observation(obs_id)["source"] == "station"


def test_an_ordinary_check_stays_tagged_app(as_user, repo):
    s = site(repo)
    obs_id = check_at(repo, as_user, USER_A, s["id"])
    assert repo.get_observation(obs_id)["source"] == "app"


def test_an_invented_source_is_rejected(as_user, repo):
    s = site(repo)
    r = as_user(USER_A).post(
        "/api/v1/observations", json={"lat": 28.6, "lng": 77.4, "site_id": s["id"], "source": "billboard"}
    )
    assert r.status_code == 422


def test_station_checks_show_a_distinct_marker_on_the_map(as_user, repo):
    s = site(repo)
    check_at(repo, as_user, USER_A, s["id"], source="station")
    points = as_user(USER_A).get("/api/v1/map").json()["points"]
    assert points and all(p["from_station"] is True for p in points)


def test_ordinary_checks_are_not_marked_as_stations(as_user, repo):
    s = site(repo)
    check_at(repo, as_user, USER_A, s["id"])
    points = as_user(USER_A).get("/api/v1/map").json()["points"]
    assert points and all(p["from_station"] is False for p in points)


# ---------------- the badge ----------------


def test_station_keeper_unlocks_on_the_first_station_check(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    badges = {b["id"]: b for b in client.get("/api/v1/me/profile").json()["badges"]}
    assert badges["station_keeper"]["current"] == 0

    check_at(repo, as_user, USER_A, s["id"], source="station")
    badges = {b["id"]: b for b in as_user(USER_A).get("/api/v1/me/profile").json()["badges"]}
    assert badges["station_keeper"]["current"] == 1
    assert badges["station_keeper"]["target"] == 1


def test_station_keeper_stays_locked_without_a_station_check(as_user, repo):
    s = site(repo)
    check_at(repo, as_user, USER_A, s["id"])
    badges = {b["id"]: b for b in as_user(USER_A).get("/api/v1/me/profile").json()["badges"]}
    assert badges["station_keeper"]["current"] == 0
    assert badges["station_keeper"]["unlocked"] is False


def test_station_keeper_is_awarded_once_however_many_scans(as_user, repo):
    s = site(repo)
    for _ in range(3):
        check_at(repo, as_user, USER_A, s["id"], source="station")
    badges = {b["id"]: b for b in as_user(USER_A).get("/api/v1/me/profile").json()["badges"]}
    assert badges["station_keeper"]["current"] == 1  # capped at the target, never 3/1


def test_every_site_gets_a_station_number(repo):
    first, second = site(repo, name="A"), site(repo, name="B", lat=28.7)
    assert first["station_number"] and second["station_number"]
    assert first["station_number"] != second["station_number"]
