"""Phase 5: GET /home, GET /me/profile, receipts, and the quest/progress services."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services import progress, quests
from app.services.badges import load_badges, progress_for, with_progress
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from tests.conftest import USER_A, USER_B, jpeg_bytes

CFG = load_game_config()
IND = load_indicators()
REQUIRED = [i.id for i in IND if i.required]
LITTER = "litter_debris"
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)  # a Friday


def gold_vote(score=3, expert=3, indicator_id=LITTER, created=None):
    return {
        "indicator_id": indicator_id,
        "score": score,
        "expert_score": expert,
        "created_at": (created or NOW).isoformat(),
    }


def onboard(repo, user_id=USER_A.id, votes=4, matched=True):
    """Give a user a practice record and an onboarded_at, as /welcome would."""
    repo.ensure_profile(user_id, f"{user_id}@test.com")
    for i in range(votes):
        gold = repo.add_gold_item(
            indicator_id=LITTER, image_path=f"public:/g{i}.jpg", expert_score=3, explanation="x" * 20
        )
        repo.insert_vote(
            {
                "voter_id": user_id,
                "answer_id": None,
                "gold_item_id": gold["id"],
                "indicator_id": LITTER,
                "score": 3 if matched else 5,
                "confidence": "sure",
                "is_gold": True,
                "correct": matched,
            }
        )
    repo.update_profile(user_id, {"onboarded_at": NOW.isoformat()})


# ---------------- quests ----------------


def test_quest_config_is_valid():
    quests.validate_config(quests.load_quests())


def test_only_measurable_quests_are_offered():
    offered = {q["type"] for q in quests.personal_quests({})}
    assert offered == set(quests.SUPPORTED_TYPES)
    assert "crew_distinct_sites_month" not in offered  # declared, but nothing to count yet


def test_quest_progress_is_capped_at_the_target():
    quest = {"id": "q", "label": "l", "description": "d", "type": "spot_check_count", "window": "today", "target": 3}
    assert quests.compute(quest, {"spot_check_count": 99})["current"] == 3
    assert quests.compute(quest, {"spot_check_count": 99})["done"] is True


def test_quest_progress_reports_partial_work():
    quest = {"id": "q", "label": "l", "description": "d", "type": "spot_check_count", "window": "today", "target": 3}
    row = quests.compute(quest, {"spot_check_count": 1})
    assert (row["current"], row["target"], row["done"]) == (1, 3, False)
    assert row["percent"] == 33


def test_todays_quest_skips_finished_ones():
    done_first = {"spot_check_count": 99, "stream_checks_week": 0}
    assert quests.todays_quest(done_first)["type"] == "stream_checks_week"


def test_no_quest_left_when_everything_is_done():
    assert quests.todays_quest({"spot_check_count": 99, "stream_checks_week": 99}) is None


def test_week_windows_start_on_monday():
    monday = quests.window_start("week", NOW)
    assert monday.weekday() == 0
    assert monday < NOW


def test_today_window_starts_at_midnight():
    assert quests.window_start("today", NOW).hour == 0


# ---------------- progress helpers ----------------


def test_verified_work_counts_only_confirmed_observations():
    observations = [
        {"id": "o1", "status": "submitted", "crowd_verified": True, "submitted_at": NOW.isoformat(), "site_id": "s1"},
        {"id": "o2", "status": "corrected", "crowd_verified": False, "submitted_at": NOW.isoformat(), "site_id": "s2"},
        {"id": "o3", "status": "submitted", "crowd_verified": False, "submitted_at": NOW.isoformat(), "site_id": "s3"},
    ]
    answers = {
        "o1": [{"indicator_id": "flow", "human_score": 3, "expert_score": None}],
        "o2": [{"indicator_id": LITTER, "human_score": 3, "expert_score": 5}],
        "o3": [{"indicator_id": "channel_form", "human_score": 3, "expert_score": None}],
    }
    work = progress.verified_work(observations, answers)
    assert work["checks"] == 2  # o3 is not verified by anyone yet
    assert work["verified_indicators"] == {"flow"}  # the corrected one does not count
    assert work["verified_sites"] == {"s1", "s2"}


def test_verified_work_falls_back_to_coordinates_without_a_site():
    observations = [
        {
            "id": "o1",
            "status": "verified",
            "crowd_verified": False,
            "submitted_at": NOW.isoformat(),
            "lat": 28.6,
            "lng": 77.4,
        }
    ]
    work = progress.verified_work(observations, {"o1": []})
    assert len(work["verified_sites"]) == 1


def test_weekly_accuracy_leaves_quiet_weeks_blank():
    votes = [gold_vote(created=NOW)]
    series = progress.weekly_accuracy(votes, weeks=3, now=NOW)
    assert len(series) == 3
    assert series[-1]["accuracy"] == 1.0 and series[-1]["n"] == 1
    assert series[0]["accuracy"] is None and series[0]["n"] == 0  # a quiet week is not a bad week


def test_weekly_accuracy_buckets_by_week():
    votes = [gold_vote(score=3, created=NOW), gold_vote(score=1, created=NOW - timedelta(weeks=1))]
    series = progress.weekly_accuracy(votes, weeks=2, now=NOW)
    assert series[0]["accuracy"] == 0.5  # |1-3|/4 -> 0.5
    assert series[1]["accuracy"] == 1.0


def test_weekly_accuracy_of_nothing_is_all_blank():
    series = progress.weekly_accuracy([], weeks=4, now=NOW)
    assert all(w["accuracy"] is None for w in series)


# ---------------- badge progress ----------------


def test_locked_badges_report_how_close_they_are():
    rule = next(b["rule"] for b in load_badges() if b["id"] == "gold_10")
    assert progress_for(rule, {"gold_matches": 4}) == (4, rule["min"])


def test_badge_progress_never_exceeds_the_target():
    rule = next(b["rule"] for b in load_badges() if b["id"] == "gold_10")
    assert progress_for(rule, {"gold_matches": 999}) == (rule["min"], rule["min"])


def test_distinct_rules_count_distinct_things():
    rule = next(b["rule"] for b in load_badges() if b["id"] == "five_indicators")
    assert progress_for(rule, {"verified_indicators": ["flow", "flow"]}) == (1, rule["min"])


def test_unlocked_badges_come_first_and_show_full_progress():
    rows = with_progress({"gold_matches": 2, "onboarded": True}, {"first_look"})
    assert rows[0]["id"] == "first_look"
    assert rows[0]["unlocked"] is True
    assert rows[0]["current"] == rows[0]["target"]
    assert len(rows) == len(load_badges())


# ---------------- GET /home ----------------


def test_home_for_a_brand_new_user_shows_only_the_practice_card(as_user, repo):
    r = as_user(USER_A).get("/api/v1/home")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["onboarded"] is False
    assert body["receipts"] == []
    assert body["lesson"] is None
    assert body["quest"] is None
    assert body["level"]["id"] == CFG["levels"][0]["id"]
    assert body["points"] == {"awarded": 0, "pending": 0}


def test_home_shows_the_header_line(as_user, repo):
    onboard(repo)
    body = as_user(USER_A).get("/api/v1/home").json()
    assert body["display_name"]
    assert body["level"]["label"]
    assert body["points"]["awarded"] >= 0


def test_home_shows_unseen_receipts_newest_first_capped_at_three(as_user, repo):
    onboard(repo)
    for i in range(5):
        repo.insert_receipt({"user_id": USER_A.id, "kind": "verified", "message": f"receipt {i}"})
    body = as_user(USER_A).get("/api/v1/home").json()
    assert len(body["receipts"]) == 3
    assert body["unseen_receipts"] == 5
    assert body["receipts"][0]["message"] == "receipt 4"


def test_home_hides_receipts_once_they_are_seen(as_user, repo):
    onboard(repo)
    receipt = repo.insert_receipt({"user_id": USER_A.id, "kind": "verified", "message": "seen one"})
    repo.mark_receipt_seen(receipt["id"])
    body = as_user(USER_A).get("/api/v1/home").json()
    assert body["receipts"] == []
    assert body["unseen_receipts"] == 0


def test_home_shows_a_lesson_when_there_is_one(as_user, repo):
    onboard(repo)
    obs = repo.create_observation(USER_A.id, 28.6, 77.4)
    repo.upsert_lesson(
        {
            "user_id": USER_A.id,
            "observation_id": obs["id"],
            "indicator_id": LITTER,
            "your_score": 2,
            "expert_score": 4,
            "why": "More waste than it looks",
        }
    )
    body = as_user(USER_A).get("/api/v1/home").json()
    assert body["lesson"]["indicator_id"] == LITTER
    assert body["lesson"]["expert_score"] == 4


def test_home_offers_todays_quest_with_live_progress(as_user, repo):
    onboard(repo)  # onboarding casts 4 gold votes today
    body = as_user(USER_A).get("/api/v1/home").json()
    quest = body["quest"]
    assert quest is not None
    # the daily Spot Check quest is already satisfied by the practice votes, so the
    # next unfinished personal quest is offered instead
    assert quest["type"] in quests.SUPPORTED_TYPES
    assert quest["current"] <= quest["target"]


def test_home_quest_counts_only_todays_votes(as_user, repo):
    onboard(repo)
    old = NOW - timedelta(days=30)
    for vote in repo.votes.values():
        vote["created_at"] = old.isoformat()
    body = as_user(USER_A).get("/api/v1/home").json()
    quest = next(q for q in [body["quest"]] if q)
    assert quest["type"] == "spot_check_count"
    assert quest["current"] == 0  # nothing today


def test_home_has_no_crew_card_yet(as_user, repo):
    onboard(repo)
    body = as_user(USER_A).get("/api/v1/home").json()
    assert "crew" not in body  # Phase 7: no broken links until it exists


def test_home_needs_a_login(repo, storage):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.db import get_repo
    from app.services.storage import get_storage

    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        assert TestClient(app).get("/api/v1/home").status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------- GET /me/profile ----------------


def test_profile_for_a_new_user_is_empty_but_valid(as_user, repo):
    r = as_user(USER_A).get("/api/v1/me/profile")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gold_votes"] == 0
    assert body["gold_accuracy"] is None  # unknown, not zero
    assert body["verified_checks"] == 0
    assert body["blind_spots"] == []
    assert len(body["skill_map"]) == len(IND)
    assert len(body["badges"]) == len(load_badges())
    assert all(w["accuracy"] is None for w in body["accuracy_by_week"])


def test_profile_reports_level_and_what_is_missing(as_user, repo):
    onboard(repo)
    body = as_user(USER_A).get("/api/v1/me/profile").json()
    assert body["level"]["id"] == "beginner"
    assert body["next_level"]["id"] == "sharp_eye"
    assert "To reach" in body["next_level"]["summary"]
    assert 0 <= body["next_level"]["percent"] <= 100


def test_profile_skill_map_uses_focus_not_weak(as_user, repo):
    onboard(repo, votes=5, matched=False)  # consistently wrong on litter
    body = as_user(USER_A).get("/api/v1/me/profile").json()
    rows = {r["indicator_id"]: r for r in body["skill_map"]}
    assert rows[LITTER]["standing"] == "focus"
    assert rows["flow"]["standing"] == "unknown"
    assert all(r["standing"] in ("strong", "ok", "focus", "unknown") for r in rows.values())


def test_profile_skill_map_marks_a_good_indicator_strong(as_user, repo):
    onboard(repo, votes=5, matched=True)
    rows = {r["indicator_id"]: r for r in as_user(USER_A).get("/api/v1/me/profile").json()["skill_map"]}
    assert rows[LITTER]["standing"] == "strong"
    assert rows[LITTER]["accuracy"] == 1.0


def test_profile_reports_a_blind_spot_in_plain_words(as_user, repo):
    onboard(repo, votes=4, matched=False)  # always 5 when the expert says 3
    body = as_user(USER_A).get("/api/v1/me/profile").json()
    assert len(body["blind_spots"]) >= 1
    spot = body["blind_spots"][0]
    assert spot["indicator_id"] == LITTER
    assert "higher" in spot["message"]
    assert len(body["blind_spots"]) <= 2


def test_profile_shows_at_most_two_blind_spots(as_user, repo):
    repo.ensure_profile(USER_A.id, "a@test.com")
    for ind_id in ("litter_debris", "flow", "channel_form"):
        for i in range(4):
            gold = repo.add_gold_item(
                indicator_id=ind_id, image_path=f"public:/{ind_id}{i}.jpg", expert_score=2, explanation="x" * 20
            )
            repo.insert_vote(
                {
                    "voter_id": USER_A.id,
                    "answer_id": None,
                    "gold_item_id": gold["id"],
                    "indicator_id": ind_id,
                    "score": 5,
                    "confidence": "sure",
                    "is_gold": True,
                    "correct": False,
                }
            )
    repo.update_profile(USER_A.id, {"onboarded_at": NOW.isoformat()})
    assert len(as_user(USER_A).get("/api/v1/me/profile").json()["blind_spots"]) == 2


def test_profile_badges_show_progress_on_locked_ones(as_user, repo):
    onboard(repo)
    badges = {b["id"]: b for b in as_user(USER_A).get("/api/v1/me/profile").json()["badges"]}
    assert badges["gold_10"]["unlocked"] is False
    assert badges["gold_10"]["current"] == 4
    assert badges["gold_10"]["target"] == 10


def test_profile_points_split_awarded_from_pending(as_user, repo):
    onboard(repo)
    from app.services import points

    repo.insert_points([points.ledger_row(USER_A.id, points.STREAM_CHECK, "a1", points.PENDING, CFG)])
    repo.insert_points([points.ledger_row(USER_A.id, points.GOLD_MATCH, "v1", points.AWARDED, CFG)])
    body = as_user(USER_A).get("/api/v1/me/profile").json()
    assert body["points"]["pending"] == CFG["points"]["stream_check_per_indicator"]
    assert body["points"]["awarded"] >= CFG["points"]["gold_match"]


def test_profile_never_leaks_another_user(as_user, repo):
    import json

    onboard(repo, USER_A.id)
    onboard(repo, USER_B.id)
    repo.update_profile(USER_B.id, {"display_name": "someone-else"})
    raw = json.dumps(as_user(USER_A).get("/api/v1/me/profile").json())
    assert "someone-else" not in raw
    assert "@test.com" not in raw  # no emails anywhere


# ---------------- receipts ----------------


def test_receipts_are_paginated_newest_first(as_user, repo):
    for i in range(5):
        repo.insert_receipt({"user_id": USER_A.id, "kind": "verified", "message": f"r{i}"})
    page = as_user(USER_A).get("/api/v1/receipts?limit=2").json()
    assert page["total"] == 5
    assert page["unseen_count"] == 5
    assert [r["message"] for r in page["items"]] == ["r4", "r3"]

    second = as_user(USER_A).get("/api/v1/receipts?limit=2&offset=2").json()
    assert [r["message"] for r in second["items"]] == ["r2", "r1"]


def test_marking_a_receipt_seen_removes_it_from_unseen(as_user, repo):
    receipt = repo.insert_receipt({"user_id": USER_A.id, "kind": "verified", "message": "well done"})
    client = as_user(USER_A)
    r = client.post(f"/api/v1/receipts/{receipt['id']}/seen")
    assert r.status_code == 200, r.text
    assert r.json()["seen"] is True
    assert client.get("/api/v1/receipts?unseen=true").json()["total"] == 0


def test_you_cannot_mark_someone_elses_receipt(as_user, repo):
    receipt = repo.insert_receipt({"user_id": USER_B.id, "kind": "verified", "message": "not yours"})
    r = as_user(USER_A).post(f"/api/v1/receipts/{receipt['id']}/seen")
    assert r.status_code == 404  # 404, not 403: don't confirm the id exists
    assert repo.get_receipt(receipt["id"])["seen"] is False


def test_an_unknown_receipt_is_404(as_user):
    assert as_user(USER_A).post("/api/v1/receipts/does-not-exist/seen").status_code == 404


def test_receipts_list_only_your_own(as_user, repo):
    repo.insert_receipt({"user_id": USER_A.id, "kind": "verified", "message": "mine"})
    repo.insert_receipt({"user_id": USER_B.id, "kind": "verified", "message": "theirs"})
    items = as_user(USER_A).get("/api/v1/receipts").json()["items"]
    assert [r["message"] for r in items] == ["mine"]


# ---------------- the proof panel's endpoint is unchanged but reachable ----------------


@pytest.mark.parametrize("path", ["/api/v1/insights/proof", "/api/v1/home", "/api/v1/me/profile"])
def test_phase5_endpoints_answer_for_a_fresh_citizen(as_user, repo, path):
    assert as_user(USER_A).get(path).status_code == 200


def test_a_real_submitted_check_shows_up_as_pending_points_on_home(as_user, repo):
    onboard(repo)
    client = as_user(USER_A)
    obs_id = client.post("/api/v1/observations", json={"lat": 28.66, "lng": 77.45}).json()["id"]
    for ind in REQUIRED:
        client.post(
            f"/api/v1/observations/{obs_id}/indicators/{ind}",
            data={"human_score": "3", "human_confidence": "sure"},
            files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
        )
    client.post(f"/api/v1/observations/{obs_id}/submit")

    body = client.get("/api/v1/home").json()
    assert body["points"]["pending"] == len(REQUIRED) * CFG["points"]["stream_check_per_indicator"]
    assert body["points"]["awarded"] >= 0
