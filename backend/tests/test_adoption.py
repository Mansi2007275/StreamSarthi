"""Phase 6: streaks, due status, adoption limits, the timeline and the monthly bonus."""

import json
from datetime import date, timedelta

from app.services import adoption, points
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from tests.conftest import USER_A, USER_B, USER_EXPERT, jpeg_bytes, make_expert

CFG = load_game_config()
MAX_SITES = CFG["max_adopted_sites"]
INTERVAL = CFG["adopted_check_interval_days"]
WARN = CFG["adopted_due_soon_days"]
BONUS = CFG["points"]["adopted_site_monthly_bonus"]
REQUIRED = [i.id for i in load_indicators() if i.required]

TODAY = date(2026, 10, 2)  # a Friday early in the month


def d(year, month, day=15):
    return date(year, month, day)


# ---------------- streaks ----------------


def test_no_checks_is_no_streak():
    assert adoption.streak_months([], TODAY) == 0


def test_a_check_this_month_is_a_one_month_streak():
    assert adoption.streak_months([d(2026, 10)], TODAY) == 1


def test_consecutive_months_build_a_streak():
    assert adoption.streak_months([d(2026, 10), d(2026, 9), d(2026, 8)], TODAY) == 3


def test_the_current_month_being_unfinished_does_not_break_the_streak():
    # nothing yet in October, but August and September were done
    assert adoption.streak_months([d(2026, 9), d(2026, 8)], TODAY) == 2


def test_a_missed_month_breaks_the_streak():
    # October and September done, August missed, July done
    assert adoption.streak_months([d(2026, 10), d(2026, 9), d(2026, 7)], TODAY) == 2


def test_a_streak_must_reach_the_present():
    # a long run that ended in spring is not a current streak
    assert adoption.streak_months([d(2026, 3), d(2026, 2), d(2026, 1)], TODAY) == 0


def test_a_streak_crosses_the_year_boundary():
    jan = date(2026, 1, 20)
    assert adoption.streak_months([d(2026, 1), d(2025, 12), d(2025, 11)], jan) == 3


def test_an_unfinished_january_still_counts_december():
    jan = date(2026, 1, 3)
    assert adoption.streak_months([d(2025, 12), d(2025, 11)], jan) == 2


def test_several_checks_in_one_month_count_once():
    assert adoption.streak_months([d(2026, 10, 1), d(2026, 10, 20), d(2026, 9)], TODAY) == 2


def test_iso_strings_are_accepted_like_dates():
    assert adoption.streak_months(["2026-10-01T08:00:00+00:00", "2026-09-14T10:00:00Z"], TODAY) == 2


def test_unparseable_dates_are_ignored():
    assert adoption.streak_months(["not a date", None, d(2026, 10)], TODAY) == 1


def test_best_streak_across_sites_is_what_the_badge_sees():
    by_site = {"a": [d(2026, 10)], "b": [d(2026, 10), d(2026, 9), d(2026, 8)]}
    assert adoption.streak_for_badge(by_site, TODAY) == 3
    assert adoption.streak_for_badge({}, TODAY) == 0


# ---------------- due status ----------------


def test_never_checked_is_due():
    assert adoption.due_status(None, TODAY, CFG) == adoption.DUE


def test_a_fresh_check_is_ok():
    assert adoption.due_status(TODAY - timedelta(days=1), TODAY, CFG) == adoption.OK


def test_the_day_before_the_warning_window_is_still_ok():
    assert adoption.due_status(TODAY - timedelta(days=INTERVAL - WARN - 1), TODAY, CFG) == adoption.OK


def test_the_warning_window_is_due_soon():
    assert adoption.due_status(TODAY - timedelta(days=INTERVAL - WARN), TODAY, CFG) == adoption.DUE_SOON
    assert adoption.due_status(TODAY - timedelta(days=INTERVAL - 1), TODAY, CFG) == adoption.DUE_SOON


def test_the_interval_itself_is_due():
    assert adoption.due_status(TODAY - timedelta(days=INTERVAL), TODAY, CFG) == adoption.DUE


def test_long_overdue_is_still_just_due():
    assert adoption.due_status(TODAY - timedelta(days=INTERVAL * 5), TODAY, CFG) == adoption.DUE


def test_the_interval_comes_from_config():
    tight = {**CFG, "adopted_check_interval_days": 7, "adopted_due_soon_days": 2}
    ten_days_ago = TODAY - timedelta(days=10)
    assert adoption.due_status(ten_days_ago, TODAY, CFG) == adoption.OK
    assert adoption.due_status(ten_days_ago, TODAY, tight) == adoption.DUE


def test_next_check_due_is_the_interval_after_the_last_one():
    last = TODAY - timedelta(days=10)
    assert adoption.next_check_due(last, CFG) == (last + timedelta(days=INTERVAL)).isoformat()
    assert adoption.next_check_due(None, CFG) is None


# ---------------- limits and the bonus rule ----------------


def test_you_can_adopt_up_to_the_limit():
    assert adoption.can_adopt(0, CFG) is True
    assert adoption.can_adopt(MAX_SITES - 1, CFG) is True
    assert adoption.can_adopt(MAX_SITES, CFG) is False


def test_the_bonus_is_owed_once_per_site_per_month():
    assert adoption.should_award_bonus("s1", "2026-10", set()) is True
    assert adoption.should_award_bonus("s1", "2026-10", {("s1", "2026-10")}) is False
    assert adoption.should_award_bonus("s1", "2026-11", {("s1", "2026-10")}) is True
    assert adoption.should_award_bonus("s2", "2026-10", {("s1", "2026-10")}) is True


def test_a_bonus_needs_a_site_and_a_month():
    assert adoption.should_award_bonus(None, "2026-10", set()) is False
    assert adoption.should_award_bonus("s1", None, set()) is False


def test_month_keys_are_sortable_strings():
    assert adoption.month_key_of("2026-01-05T00:00:00Z") == "2026-01"
    assert adoption.month_key_of(None) is None


# ---------------- endpoints ----------------


def site(repo, name="Hindon Ghat", lat=28.6692, lng=77.4538):
    return repo.create_site(lat, lng, name)


def submit_check(repo, as_user, user, site_id, submitted_at=None, verified=False):
    """A real submitted check at a site, optionally already verified."""
    client = as_user(user)
    obs_id = client.post(
        "/api/v1/observations", json={"lat": 28.6692, "lng": 77.4538, "site_id": site_id}
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
    if verified:
        fields["crowd_verified"] = True
    if fields:
        repo.update_observation(obs_id, fields)
    return obs_id


def test_adopting_a_site_shows_it_on_my_stream(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    r = client.post(f"/api/v1/sites/{s['id']}/adopt")
    assert r.status_code == 200, r.text
    assert r.json()["adopted"] is True
    assert r.json()["adopted_count"] == 1

    body = client.get("/api/v1/my-stream").json()
    assert len(body["sites"]) == 1
    assert body["sites"][0]["name"] == "Hindon Ghat"
    assert body["sites"][0]["due_status"] == "due"  # never checked
    assert body["max_sites"] == MAX_SITES
    assert body["can_adopt_more"] is True


def test_adopting_twice_is_idempotent(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    r = client.post(f"/api/v1/sites/{s['id']}/adopt")
    assert r.status_code == 200
    assert r.json()["adopted_count"] == 1
    assert len(client.get("/api/v1/my-stream").json()["sites"]) == 1


def test_a_fourth_site_is_refused_with_a_clear_message(as_user, repo):
    client = as_user(USER_A)
    for i in range(MAX_SITES):
        s = site(repo, name=f"Site {i}", lat=28.6 + i / 100)
        assert client.post(f"/api/v1/sites/{s['id']}/adopt").status_code == 200

    extra = site(repo, name="One too many", lat=29.0)
    r = client.post(f"/api/v1/sites/{extra['id']}/adopt")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ADOPTION_LIMIT"
    assert str(MAX_SITES) in r.json()["error"]["message"]
    assert client.get("/api/v1/my-stream").json()["can_adopt_more"] is False


def test_releasing_then_re_adopting_works(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")

    r = client.post(f"/api/v1/sites/{s['id']}/release")
    assert r.status_code == 200
    assert r.json()["adopted"] is False
    assert client.get("/api/v1/my-stream").json()["sites"] == []

    assert client.post(f"/api/v1/sites/{s['id']}/adopt").status_code == 200
    assert len(client.get("/api/v1/my-stream").json()["sites"]) == 1


def test_releasing_keeps_the_old_row_as_history(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    client.post(f"/api/v1/sites/{s['id']}/release")
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    assert len(repo.adoptions) == 2  # released, not overwritten


def test_releasing_something_you_never_adopted_is_harmless(as_user, repo):
    s = site(repo)
    r = as_user(USER_A).post(f"/api/v1/sites/{s['id']}/release")
    assert r.status_code == 200
    assert r.json()["adopted"] is False


def test_adopting_an_unknown_site_is_404(as_user):
    assert as_user(USER_A).post("/api/v1/sites/00000000-0000-0000-0000-000000000000/adopt").status_code == 404


def test_my_stream_is_empty_for_a_new_user(as_user, repo):
    body = as_user(USER_A).get("/api/v1/my-stream").json()
    assert body["sites"] == []
    assert body["can_adopt_more"] is True


def test_my_stream_reports_last_check_and_streak(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    submit_check(repo, as_user, USER_A, s["id"])

    card = client.get("/api/v1/my-stream").json()["sites"][0]
    assert card["checks"] == 1
    assert card["last_check"] is not None
    assert card["streak_months"] == 1
    assert card["due_status"] == "ok"
    assert card["next_check_due"] is not None


def test_my_stream_rounds_the_coordinates(as_user, repo):
    s = site(repo, lat=28.669212345, lng=77.453787654)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    card = client.get("/api/v1/my-stream").json()["sites"][0]
    assert card["lat"] == 28.669  # ~100 m, not a doorstep
    assert card["lng"] == 77.454


def test_my_stream_counts_other_guardians_without_naming_them(as_user, repo):
    s = site(repo)
    as_user(USER_A).post(f"/api/v1/sites/{s['id']}/adopt")
    submit_check(repo, as_user, USER_B, s["id"])

    # as_user sets a global dependency override, so switch back to USER_A explicitly.
    body = as_user(USER_A).get("/api/v1/my-stream").json()
    card = body["sites"][0]
    assert card["others_this_month"] == 1
    assert card["checks"] == 0  # none of them are mine
    assert USER_B.id not in json.dumps(body)


# ---------------- timeline ----------------


def test_the_timeline_has_one_entry_per_month(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-10-01T09:00:00+00:00")
    submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-09-05T09:00:00+00:00")

    body = client.get(f"/api/v1/sites/{s['id']}/timeline").json()
    assert [e["month"] for e in body["entries"]] == ["2026-10", "2026-09"]  # newest first
    assert body["streak_months"] >= 1


def test_several_checks_in_a_month_collapse_into_one_entry(as_user, repo):
    s = site(repo)
    submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-10-01T09:00:00+00:00")
    submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-10-20T09:00:00+00:00")

    entries = as_user(USER_A).get(f"/api/v1/sites/{s['id']}/timeline").json()["entries"]
    assert len(entries) == 1
    assert entries[0]["checks"] == 2
    assert entries[0]["mine"] == 2


def test_the_timeline_shows_the_one_health_reading_and_worst_indicators(as_user, repo):
    s = site(repo)
    obs_id = submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-10-01T09:00:00+00:00")
    repo.update_observation(
        obs_id,
        {
            "one_health": {
                "level": "poor",
                "drivers": [{"indicator_id": "water_colour", "label": "Water colour", "severity": 0.9}],
            }
        },
    )
    entry = as_user(USER_A).get(f"/api/v1/sites/{s['id']}/timeline").json()["entries"][0]
    assert entry["one_health_level"] == "poor"
    assert entry["worst_indicators"] == ["Water colour"]


def test_a_month_is_verified_when_any_check_in_it_was(as_user, repo):
    s = site(repo)
    submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-10-01T09:00:00+00:00")
    submit_check(repo, as_user, USER_A, s["id"], submitted_at="2026-10-20T09:00:00+00:00", verified=True)
    assert as_user(USER_A).get(f"/api/v1/sites/{s['id']}/timeline").json()["entries"][0]["verified"] is True


def test_the_timeline_never_leaks_who_checked_the_site(as_user, repo):
    s = site(repo)
    repo.ensure_profile(USER_B.id, "someone@private.test")
    repo.update_profile(USER_B.id, {"display_name": "someone-else"})
    submit_check(repo, as_user, USER_B, s["id"], submitted_at="2026-10-01T09:00:00+00:00")

    raw = json.dumps(as_user(USER_A).get(f"/api/v1/sites/{s['id']}/timeline").json())
    assert USER_B.id not in raw
    assert "someone-else" not in raw
    assert "@private.test" not in raw
    assert "user_id" not in raw
    assert "photo" not in raw


def test_the_timeline_of_an_unchecked_site_is_empty_but_valid(as_user, repo):
    s = site(repo)
    body = as_user(USER_A).get(f"/api/v1/sites/{s['id']}/timeline").json()
    assert body["entries"] == []
    assert body["adopted"] is False
    assert body["due_status"] == "due"


def test_an_unknown_site_timeline_is_404(as_user):
    assert as_user(USER_A).get("/api/v1/sites/nope/timeline").status_code == 404


# ---------------- the monthly bonus ----------------


def test_the_bonus_lands_when_a_check_at_an_adopted_site_is_verified(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    obs_id = submit_check(repo, as_user, USER_A, s["id"])

    make_expert(repo)
    as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Looks good"})

    bonuses = [p for p in repo.list_points(USER_A.id) if p["reason"] == points.ADOPTED_BONUS]
    assert len(bonuses) == 1
    assert bonuses[0]["amount"] == BONUS
    assert bonuses[0]["status"] == "awarded"
    assert any(r["kind"] == "used_in_trend" for r in repo.list_receipts(USER_A.id))


def test_no_bonus_before_verification(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    submit_check(repo, as_user, USER_A, s["id"])
    assert [p for p in repo.list_points(USER_A.id) if p["reason"] == points.ADOPTED_BONUS] == []


def test_no_bonus_for_a_site_you_have_not_adopted(as_user, repo):
    s = site(repo)
    obs_id = submit_check(repo, as_user, USER_A, s["id"])
    make_expert(repo)
    as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Looks good"})
    assert [p for p in repo.list_points(USER_A.id) if p["reason"] == points.ADOPTED_BONUS] == []


def test_only_one_bonus_per_site_per_month(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    make_expert(repo)

    for _ in range(2):
        obs_id = submit_check(repo, as_user, USER_A, s["id"])
        as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "approve", "note": "Looks good"})

    bonuses = [p for p in repo.list_points(USER_A.id) if p["reason"] == points.ADOPTED_BONUS]
    assert len(bonuses) == 1  # volume in one month earns one bonus, not two


def test_a_rejected_check_earns_no_bonus(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    obs_id = submit_check(repo, as_user, USER_A, s["id"])

    make_expert(repo)
    as_user(USER_EXPERT).post(f"/api/v1/review/{obs_id}", json={"action": "reject", "note": "Photos unusable"})
    assert [p for p in repo.list_points(USER_A.id) if p["reason"] == points.ADOPTED_BONUS] == []


# ---------------- badge + home card ----------------


def test_steady_guardian_unlocks_on_a_three_month_streak(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    today = adoption.today_utc()
    for back in range(3):
        month = today.month - back
        year = today.year + (0 if month > 0 else -1)
        month = month if month > 0 else month + 12
        submit_check(repo, as_user, USER_A, s["id"], submitted_at=f"{year:04d}-{month:02d}-10T09:00:00+00:00")

    badges = {b["id"]: b for b in client.get("/api/v1/me/profile").json()["badges"]}
    assert badges["steady_guardian"]["current"] == 3
    assert client.get("/api/v1/my-stream").json()["sites"][0]["streak_months"] == 3


def test_a_single_month_does_not_unlock_steady_guardian(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    submit_check(repo, as_user, USER_A, s["id"])
    badges = {b["id"]: b for b in client.get("/api/v1/me/profile").json()["badges"]}
    assert badges["steady_guardian"]["unlocked"] is False
    assert badges["steady_guardian"]["current"] == 1


def test_home_nags_about_an_overdue_adopted_site(as_user, repo):
    s = site(repo, name="Karhera Drain")
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    repo.update_profile(USER_A.id, {"onboarded_at": "2026-01-01T00:00:00+00:00"})

    due = client.get("/api/v1/home").json()["due_site"]
    assert due is not None
    assert due["name"] == "Karhera Drain"
    assert due["due_status"] == "due"  # never checked


def test_home_says_nothing_about_a_site_checked_yesterday(as_user, repo):
    s = site(repo)
    client = as_user(USER_A)
    client.post(f"/api/v1/sites/{s['id']}/adopt")
    repo.update_profile(USER_A.id, {"onboarded_at": "2026-01-01T00:00:00+00:00"})
    submit_check(repo, as_user, USER_A, s["id"])
    assert client.get("/api/v1/home").json()["due_site"] is None


def test_home_has_no_due_card_without_adoptions(as_user, repo):
    repo.ensure_profile(USER_A.id, "a@test.com")
    repo.update_profile(USER_A.id, {"onboarded_at": "2026-01-01T00:00:00+00:00"})
    assert as_user(USER_A).get("/api/v1/home").json()["due_site"] is None


def test_my_stream_needs_a_login(repo, storage):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.db import get_repo
    from app.services.storage import get_storage

    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        client = TestClient(app)
        assert client.get("/api/v1/my-stream").status_code == 401
        assert client.post("/api/v1/sites/x/adopt").status_code == 401
        assert client.post("/api/v1/sites/x/release").status_code == 401
        assert client.get("/api/v1/sites/x/timeline").status_code == 401
    finally:
        app.dependency_overrides.clear()
