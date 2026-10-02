from app.services.game_config import load_game_config
from app.services.sites import haversine_m, nearest_site
from tests.conftest import USER_A

CFG = load_game_config()
RADIUS = CFG["stream_check"]["site_match_radius_m"]
LAT, LNG = 28.6692, 77.4538

# At this latitude 1 degree of latitude is ~110.9 km, so these are handy known offsets.
ONE_METRE_LAT = 1 / 110_900


def site(site_id="s1", lat=LAT, lng=LNG, name="Hindon Ghat"):
    return {"id": site_id, "lat": lat, "lng": lng, "name": name}


def offset(metres: float) -> dict:
    return site(lat=LAT + metres * ONE_METRE_LAT)


# ---------------- haversine ----------------


def test_distance_to_itself_is_zero():
    assert haversine_m(LAT, LNG, LAT, LNG) == 0


def test_one_degree_of_latitude_is_about_111_km():
    assert 110_000 < haversine_m(0, 0, 1, 0) < 112_000


def test_a_hundred_metres_measures_as_a_hundred_metres():
    assert 99 < haversine_m(LAT, LNG, LAT + 100 * ONE_METRE_LAT, LNG) < 101


def test_distance_is_symmetric():
    a = haversine_m(LAT, LNG, 28.70, 77.50)
    b = haversine_m(28.70, 77.50, LAT, LNG)
    assert abs(a - b) < 0.001


def test_antipodal_points_do_not_blow_up():
    # guards the asin domain clamp
    assert haversine_m(0, 0, 0, 180) > 20_000_000


# ---------------- nearest_site ----------------


def test_a_site_at_the_same_spot_matches():
    match = nearest_site(LAT, LNG, [site()], CFG)
    assert match["site"]["id"] == "s1"
    assert match["distance_m"] == 0


def test_a_site_just_inside_the_radius_matches():
    match = nearest_site(LAT, LNG, [offset(RADIUS - 10)], CFG)
    assert match is not None
    assert match["distance_m"] < RADIUS


def test_a_site_just_outside_the_radius_does_not():
    assert nearest_site(LAT, LNG, [offset(RADIUS + 50)], CFG) is None


def test_the_closest_of_several_wins():
    sites = [
        site("far", lat=LAT + 120 * ONE_METRE_LAT),
        site("near", lat=LAT + 20 * ONE_METRE_LAT),
        site("mid", lat=LAT + 60 * ONE_METRE_LAT),
    ]
    assert nearest_site(LAT, LNG, sites, CFG)["site"]["id"] == "near"


def test_no_sites_on_record_is_no_match():
    assert nearest_site(LAT, LNG, [], CFG) is None


def test_no_gps_fix_is_no_match():
    assert nearest_site(None, None, [site()], CFG) is None
    assert nearest_site(LAT, None, [site()], CFG) is None


def test_sites_without_coordinates_are_skipped():
    assert nearest_site(LAT, LNG, [{"id": "broken", "lat": None, "lng": None}], CFG) is None


def test_the_radius_comes_from_config():
    tight = {**CFG, "stream_check": {**CFG["stream_check"], "site_match_radius_m": 5}}
    assert nearest_site(LAT, LNG, [offset(50)], CFG) is not None
    assert nearest_site(LAT, LNG, [offset(50)], tight) is None


# ---------------- the endpoint ----------------


def test_near_returns_the_matching_site(as_user, repo):
    saved = repo.create_site(LAT, LNG, "Hindon Ghat")
    r = as_user(USER_A).get(f"/api/v1/sites/near?lat={LAT}&lng={LNG}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["site"]["id"] == saved["id"]
    assert body["site"]["name"] == "Hindon Ghat"
    assert body["distance_m"] == 0
    assert body["radius_m"] == RADIUS


def test_near_returns_null_when_nothing_is_close(as_user, repo):
    repo.create_site(28.0, 77.0, "Far away")
    body = as_user(USER_A).get(f"/api/v1/sites/near?lat={LAT}&lng={LNG}").json()
    assert body["site"] is None
    assert body["distance_m"] is None


def test_near_leaks_nothing_but_the_name_and_distance(as_user, repo):
    repo.create_site(LAT, LNG, "Hindon Ghat")
    body = as_user(USER_A).get(f"/api/v1/sites/near?lat={LAT}&lng={LNG}").json()
    assert set(body["site"].keys()) == {"id", "name"}  # no coordinates, no who checked it


def test_near_validates_coordinates(as_user):
    assert as_user(USER_A).get("/api/v1/sites/near?lat=999&lng=0").status_code == 422
    assert as_user(USER_A).get("/api/v1/sites/near?lat=28.6").status_code == 422


def test_near_needs_a_login(repo, storage):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.db import get_repo
    from app.services.storage import get_storage

    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        assert TestClient(app).get("/api/v1/sites/near?lat=28.6&lng=77.4").status_code == 401
    finally:
        app.dependency_overrides.clear()
