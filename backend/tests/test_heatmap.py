from app.services.heatmap import compute_disagreement
from app.services.indicators import load_indicators
from tests.conftest import USER_A, USER_EXPERT, jpeg_bytes, make_expert

IND = load_indicators()
FIRST = IND[0]


def _row(human, ai, conf=0.9, expert=None):
    return {
        "indicator_id": FIRST.id,
        "human_score": human,
        "ai_score": ai,
        "ai_confidence": conf,
        "expert_score": expert,
    }


def test_perfect_agreement_has_zero_diff_and_strong_rate():
    rows = [_row(2, 2), _row(3, 3)]
    result = next(r for r in compute_disagreement(rows, IND) if r["indicator_id"] == FIRST.id)
    assert result["n"] == 2
    assert result["mean_abs_diff"] == 0
    assert result["strong_rate"] == 0


def test_strong_disagreement_counted():
    rows = [_row(1, 5, conf=0.9), _row(2, 2, conf=0.9)]  # first is strong (diff 4, conf > 0.7)
    result = next(r for r in compute_disagreement(rows, IND) if r["indicator_id"] == FIRST.id)
    assert result["strong_rate"] == 0.5


def test_low_confidence_disagreement_not_strong():
    rows = [_row(1, 5, conf=0.5)]
    result = next(r for r in compute_disagreement(rows, IND) if r["indicator_id"] == FIRST.id)
    assert result["strong_rate"] == 0


def test_human_and_ai_wrong_rate_use_expert_score():
    rows = [_row(1, 2, expert=2), _row(3, 3, expert=3)]  # first: human wrong, ai right. second: both right
    result = next(r for r in compute_disagreement(rows, IND) if r["indicator_id"] == FIRST.id)
    assert result["human_wrong_rate"] == 0.5
    assert result["ai_wrong_rate"] == 0.0


def test_matrix_diagonal_counts():
    rows = [_row(1, 1), _row(1, 1), _row(2, 2)]
    result = next(r for r in compute_disagreement(rows, IND) if r["indicator_id"] == FIRST.id)
    lo, _ = FIRST.scale
    assert result["matrix"][1 - lo][1 - lo] == 2
    assert result["matrix"][2 - lo][2 - lo] == 1


def test_no_data_gives_none_rates_not_errors():
    result = next(r for r in compute_disagreement([], IND) if r["indicator_id"] == FIRST.id)
    assert result["n"] == 0
    assert result["mean_abs_diff"] is None
    assert result["human_wrong_rate"] is None


def _submit(as_user, user, score=2):
    c = as_user(user)
    obs = c.post("/api/v1/observations", json={"lat": 1.0, "lng": 1.0}).json()
    for ind in [i.id for i in IND if i.required]:
        c.post(
            f"/api/v1/observations/{obs['id']}/indicators/{ind}",
            data={"human_score": str(score)},
            files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")},
        )
    c.post(f"/api/v1/observations/{obs['id']}/submit")
    return obs["id"]


def test_endpoint_requires_expert_role(as_user):
    r = as_user(USER_A).get("/api/v1/insights/disagreement")
    assert r.status_code == 403


def test_endpoint_returns_one_row_per_indicator(as_user, repo):
    make_expert(repo)
    _submit(as_user, USER_A)
    r = as_user(USER_EXPERT).get("/api/v1/insights/disagreement")
    assert r.status_code == 200, r.text
    ids = {row["indicator_id"] for row in r.json()}
    assert ids == {i.id for i in IND}
