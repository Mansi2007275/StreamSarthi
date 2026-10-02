"""Phase 3: the confidence step, the Disagreement Card trigger, routing and the submit result."""

from app.models.schemas import AIOpinion
from app.routers import observations as obs_router
from app.services.consistency import check_observation, is_disagreement, is_strong_disagreement
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from tests.conftest import USER_A, jpeg_bytes

CFG = load_game_config()
SC = CFG["stream_check"]
REQUIRED = [i.id for i in load_indicators() if i.required]
STREAM_POINTS = CFG["points"]["stream_check_per_indicator"]
FIRST = REQUIRED[0]


def ai_says(monkeypatch, score, confidence=0.8, can_assess=True):
    async def fake(image_bytes, ind, settings=None):
        return AIOpinion(
            suggested_score=score,
            confidence=confidence,
            visible_evidence=["brown water", "plastic bottle"],
            reason="Demo reason",
            can_assess=can_assess,
            retake_tip="Stand closer to the water." if not can_assess else "",
        )

    monkeypatch.setattr(obs_router.ai_opinion, "get_opinion", fake)


def start(client, **body):
    return client.post("/api/v1/observations", json={"lat": 28.6692, "lng": 77.4538, **body})


def answer(client, obs_id, indicator_id, score=3, confidence="sure"):
    data = {"human_score": str(score)}
    if confidence is not None:
        data["human_confidence"] = confidence
    return client.post(
        f"/api/v1/observations/{obs_id}/indicators/{indicator_id}",
        data=data,
        files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
    )


def answer_all(client, obs_id, score=3, confidence="sure", unsure=()):
    for ind in REQUIRED:
        answer(client, obs_id, ind, score, "guess" if ind in unsure else confidence)


# ---------------- the confidence step ----------------


def test_confidence_is_stored_with_the_answer(as_user, repo):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    r = answer(client, obs_id, FIRST, 3, "somewhat")
    assert r.status_code == 200, r.text
    assert r.json()["human_confidence"] == "somewhat"
    assert repo.get_answer(obs_id, FIRST)["human_confidence"] == "somewhat"


def test_every_confidence_value_is_accepted(as_user):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    for value in ("sure", "somewhat", "guess"):
        assert answer(client, obs_id, FIRST, 3, value).json()["human_confidence"] == value


def test_an_invented_confidence_value_is_rejected(as_user):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    assert answer(client, obs_id, FIRST, 3, "certain").status_code == 422


def test_confidence_is_optional(as_user, repo):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    assert answer(client, obs_id, FIRST, 3, None).status_code == 200
    assert repo.get_answer(obs_id, FIRST)["human_confidence"] is None


def test_the_detail_view_shows_the_confidence(as_user):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    answer(client, obs_id, FIRST, 3, "guess")
    detail = client.get(f"/api/v1/observations/{obs_id}").json()
    first = next(a for a in detail["answers"] if a["indicator_id"] == FIRST)
    assert first["human_confidence"] == "guess"


def test_asking_for_an_expert_marks_a_guess_without_losing_the_score(as_user, repo):
    """The Disagreement Card's third button: "Not sure - ask an expert"."""
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    answer(client, obs_id, FIRST, 2, "sure")

    r = client.patch(
        f"/api/v1/observations/{obs_id}/indicators/{FIRST}",
        json={"used_ai_answer": False, "human_score": 2, "human_confidence": "guess"},
    )
    assert r.status_code == 200, r.text
    saved = repo.get_answer(obs_id, FIRST)
    assert saved["human_confidence"] == "guess"
    assert saved["human_score"] == 2  # never discarded
    assert saved["used_ai_answer"] is False


def test_changing_your_mind_keeps_the_ai_answer_on_record(as_user, repo):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    answer(client, obs_id, FIRST, 1, "sure")
    client.patch(
        f"/api/v1/observations/{obs_id}/indicators/{FIRST}",
        json={"used_ai_answer": True, "human_score": 1},
    )
    saved = repo.get_answer(obs_id, FIRST)
    assert saved["human_score"] == 1 and saved["ai_score"] == 3  # both kept, per the rules


# ---------------- the Disagreement Card trigger ----------------


def test_a_two_point_gap_triggers_the_card():
    assert is_disagreement({"human_score": 1, "ai_score": 3, "ai_can_assess": True}, CFG)


def test_a_one_point_gap_does_not():
    assert not is_disagreement({"human_score": 2, "ai_score": 3, "ai_can_assess": True}, CFG)


def test_no_card_when_the_ai_cannot_assess():
    assert not is_disagreement({"human_score": 1, "ai_score": 3, "ai_can_assess": False}, CFG)


def test_no_card_without_both_scores():
    assert not is_disagreement({"human_score": None, "ai_score": 3, "ai_can_assess": True}, CFG)
    assert not is_disagreement({"human_score": 1, "ai_score": None, "ai_can_assess": True}, CFG)


def test_a_hesitant_ai_still_shows_the_card_though_it_does_not_route():
    """The two rules differ on purpose: the citizen should look again even when the AI is unsure,
    but an unsure AI is not grounds for spending an expert's time."""
    answer_row = {"human_score": 1, "ai_score": 4, "ai_confidence": 0.3, "ai_can_assess": True}
    assert is_disagreement(answer_row, CFG)
    assert not is_strong_disagreement(answer_row)


def test_the_card_threshold_comes_from_config():
    loose = {**CFG, "stream_check": {**SC, "disagreement_card_min_diff": 1}}
    row = {"human_score": 2, "ai_score": 3, "ai_can_assess": True}
    assert not is_disagreement(row, CFG)
    assert is_disagreement(row, loose)


def test_the_endpoint_flags_a_disagreement(as_user, monkeypatch):
    client = as_user(USER_A)
    ai_says(monkeypatch, 5)
    obs_id = start(client).json()["id"]
    body = answer(client, obs_id, FIRST, 1).json()
    assert body["ai_score"] == 5
    assert body["disagreement"] is True


def test_the_endpoint_does_not_flag_agreement(as_user, monkeypatch):
    client = as_user(USER_A)
    ai_says(monkeypatch, 3)
    obs_id = start(client).json()["id"]
    assert answer(client, obs_id, FIRST, 3).json()["disagreement"] is False


def test_no_disagreement_flag_when_the_ai_gives_up(as_user, monkeypatch):
    client = as_user(USER_A)
    ai_says(monkeypatch, None, can_assess=False)
    obs_id = start(client).json()["id"]
    body = answer(client, obs_id, FIRST, 1).json()
    assert body["can_assess"] is False
    assert body["disagreement"] is False
    assert body["retake_tip"]  # the client needs something to show on the Retake/Skip card


# ---------------- citizen_unsure routing ----------------


def test_a_guess_becomes_a_routing_reason():
    answers = [{"indicator_id": FIRST, "human_score": 3, "human_confidence": "guess"}]
    codes = [i["code"] for i in check_observation({"lat": 1, "lng": 1}, answers, CFG)]
    assert "citizen_unsure" in codes


def test_the_reason_names_the_indicators_the_citizen_doubted():
    answers = [{"indicator_id": FIRST, "human_score": 3, "human_confidence": "guess"}]
    issue = next(i for i in check_observation({"lat": 1, "lng": 1}, answers, CFG) if i["code"] == "citizen_unsure")
    assert issue["indicators"] == [FIRST]
    assert next(i.label for i in load_indicators() if i.id == FIRST) in issue["message"]


def test_being_sure_is_not_a_routing_reason():
    answers = [{"indicator_id": FIRST, "human_score": 3, "human_confidence": "sure"}]
    codes = [i["code"] for i in check_observation({"lat": 1, "lng": 1}, answers, CFG)]
    assert "citizen_unsure" not in codes


def test_how_many_guesses_it_takes_is_configurable():
    strict = {**CFG, "stream_check": {**SC, "unsure_answers_to_review": 2}}
    one_guess = [{"indicator_id": FIRST, "human_score": 3, "human_confidence": "guess"}]
    codes = [i["code"] for i in check_observation({"lat": 1, "lng": 1}, one_guess, strict)]
    assert "citizen_unsure" not in codes


def test_an_unsure_answer_sends_the_whole_observation_to_an_expert(as_user, repo):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    answer_all(client, obs_id, score=3, unsure={FIRST})

    body = client.post(f"/api/v1/observations/{obs_id}/submit").json()
    assert body["status"] == "needs_review"
    assert body["routed_to"] == "expert"
    assert "citizen_unsure" in body["routing_reasons"]
    # a high trust score must not talk us out of the citizen's own doubt
    assert body["trust_score"] > 60


def test_a_confident_observation_goes_to_the_crowd(as_user):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    answer_all(client, obs_id, score=3)

    body = client.post(f"/api/v1/observations/{obs_id}/submit").json()
    assert body["status"] == "submitted"
    assert body["routed_to"] == "crowd"
    assert body["routing_reasons"] == []


# ---------------- the submit result ----------------


def test_submit_reports_the_points_now_pending(as_user):
    client = as_user(USER_A)
    obs_id = start(client).json()["id"]
    answer_all(client, obs_id)
    body = client.post(f"/api/v1/observations/{obs_id}/submit").json()
    assert body["pending_points"] == len(REQUIRED) * STREAM_POINTS


def test_pending_points_count_only_this_observation(as_user):
    client = as_user(USER_A)
    first_id = start(client).json()["id"]
    answer_all(client, first_id)
    client.post(f"/api/v1/observations/{first_id}/submit")

    second_id = start(client).json()["id"]
    answer_all(client, second_id)
    body = client.post(f"/api/v1/observations/{second_id}/submit").json()
    assert body["pending_points"] == len(REQUIRED) * STREAM_POINTS  # not doubled


# ---------------- sites in the flow ----------------


def test_confirming_a_nearby_site_attaches_it(as_user, repo):
    site = repo.create_site(28.6692, 77.4538, "Hindon Ghat")
    client = as_user(USER_A)
    created = start(client, site_id=site["id"]).json()
    assert created["site_id"] == site["id"]
    assert created["site_name"] == "Hindon Ghat"
    assert repo.get_observation(created["id"])["site_id"] == site["id"]


def test_an_unknown_site_is_404(as_user):
    assert start(as_user(USER_A), site_id="00000000-0000-0000-0000-000000000000").status_code == 404


def test_naming_a_new_place_creates_that_site(as_user, repo):
    client = as_user(USER_A)
    created = start(client, site_name="Karhera Drain").json()
    assert created["site_name"] == "Karhera Drain"
    assert repo.get_site(created["site_id"])["name"] == "Karhera Drain"


def test_an_unnamed_new_place_still_gets_a_site_on_submit(as_user, repo):
    client = as_user(USER_A)
    created = start(client).json()
    assert created["site_id"] is None
    answer_all(client, created["id"])
    client.post(f"/api/v1/observations/{created['id']}/submit")

    site_id = repo.get_observation(created["id"])["site_id"]
    assert site_id is not None
    assert repo.get_site(site_id)["name"] is None  # shows as coordinates until named


def test_submit_keeps_the_site_the_citizen_chose(as_user, repo):
    site = repo.create_site(28.6692, 77.4538, "Hindon Ghat")
    client = as_user(USER_A)
    created = start(client, site_id=site["id"]).json()
    answer_all(client, created["id"])
    client.post(f"/api/v1/observations/{created['id']}/submit")

    assert repo.get_observation(created["id"])["site_id"] == site["id"]
    assert len(repo.list_sites()) == 1  # no duplicate created


def test_no_site_is_invented_without_a_gps_fix(as_user, repo):
    client = as_user(USER_A)
    created = client.post("/api/v1/observations", json={"lat": None, "lng": None}).json()
    answer_all(client, created["id"])
    client.post(f"/api/v1/observations/{created['id']}/submit")

    assert repo.get_observation(created["id"])["site_id"] is None
    assert repo.list_sites() == []


def test_a_site_name_without_coordinates_is_not_invented(as_user, repo):
    client = as_user(USER_A)
    created = client.post("/api/v1/observations", json={"lat": None, "lng": None, "site_name": "Nowhere"}).json()
    assert created["site_id"] is None
    assert repo.list_sites() == []
