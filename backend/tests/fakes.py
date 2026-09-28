import uuid

from app.services.db import now_iso


class FakeRepo:
    def __init__(self):
        self.profiles: dict[str, dict] = {}
        self.observations: dict[str, dict] = {}
        self.answers: dict[tuple[str, str], dict] = {}

    def ensure_profile(self, user_id, email):
        self.profiles.setdefault(user_id, {"id": user_id, "role": "citizen", "observer_accuracy": 0.5})

    def create_observation(self, user_id, lat, lng):
        oid = str(uuid.uuid4())
        obs = {
            "id": oid,
            "user_id": user_id,
            "lat": lat,
            "lng": lng,
            "status": "draft",
            "created_at": now_iso(),
            "submitted_at": None,
            "trust_score": None,
        }
        self.observations[oid] = obs
        return dict(obs)

    def get_observation(self, obs_id):
        o = self.observations.get(obs_id)
        return dict(o) if o else None

    def list_observations(self, user_id, offset, limit):
        mine = sorted(
            (o for o in self.observations.values() if o["user_id"] == user_id),
            key=lambda o: o["created_at"],
            reverse=True,
        )
        return [dict(o) for o in mine[offset : offset + limit]], len(mine)

    def update_observation(self, obs_id, fields):
        self.observations[obs_id].update(fields)
        return dict(self.observations[obs_id])

    def upsert_answer(self, row):
        key = (row["observation_id"], row["indicator_id"])
        existing = self.answers.get(key, {})
        existing.update(row)
        self.answers[key] = existing
        return dict(existing)

    def get_answer(self, obs_id, indicator_id):
        a = self.answers.get((obs_id, indicator_id))
        return dict(a) if a else None

    def update_answer(self, obs_id, indicator_id, fields):
        self.answers[(obs_id, indicator_id)].update(fields)
        return dict(self.answers[(obs_id, indicator_id)])

    def list_answers(self, obs_id):
        return [dict(a) for (o, _), a in self.answers.items() if o == obs_id]

    def recent_phashes(self, user_id, exclude_obs_id, limit=50):
        obs_ids = {o["id"] for o in self.observations.values() if o["user_id"] == user_id and o["id"] != exclude_obs_id}
        hashes = [
            a["photo_quality"]["phash"]
            for (oid, _), a in reversed(list(self.answers.items()))
            if oid in obs_ids and a.get("photo_quality")
        ]
        return hashes[:limit]

    def get_profile(self, user_id):
        p = self.profiles.get(user_id)
        return dict(p) if p else None


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def upload(self, path, data):
        self.files[path] = data

    def signed_url(self, path):
        return f"https://signed.example/{path}" if path in self.files else None
