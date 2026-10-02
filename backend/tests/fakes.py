import uuid

from app.services.db import AuditConflict, now_iso


class FakeRepo:
    def __init__(self):
        self.profiles: dict[str, dict] = {}
        self.observations: dict[str, dict] = {}
        self.answers: dict[tuple[str, str], dict] = {}
        self.audit_events: dict[str, list[dict]] = {}
        self._audit_seen: set[tuple[str, str]] = set()
        self._audit_next_id = 1
        self.lessons: dict[str, dict] = {}
        self._lesson_by_key: dict[tuple[str, str], str] = {}
        self._lesson_next_id = 1
        # Guardians (Phase 1)
        self.gold_items: dict[str, dict] = {}
        self.votes: dict[str, dict] = {}
        self.points: list[dict] = []
        self.receipts: dict[str, dict] = {}
        self.user_badges: list[dict] = []
        self.sites: dict[str, dict] = {}
        self.crews: dict[str, str] = {}  # user_id -> crew_id (Phase 7 fills this for real)
        self.adoptions: dict[str, dict] = {}

    def ensure_profile(self, user_id, email):
        self.profiles.setdefault(
            user_id,
            {
                "id": user_id,
                "role": "citizen",
                "observer_accuracy": 0.5,
                "display_name": (email or "user").split("@")[0],
            },
        )

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
            # migration 005 defaults, so the fake matches the real table
            "crowd_verified": False,
            "crew_id": None,
            "site_id": None,
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
        existing.setdefault("id", str(uuid.uuid4()))  # the real table generates one
        existing.setdefault("crowd_votes", 0)
        existing.setdefault("crowd_status", "pending")
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

    def update_profile(self, user_id, fields):
        self.profiles[user_id].update(fields)
        return dict(self.profiles[user_id])

    def list_review_queue(self, exclude_user_id, status, offset, limit):
        rows = [o for o in self.observations.values() if o["status"] == status and o["user_id"] != exclude_user_id]

        def sort_key(o):
            ts = o.get("trust_score")
            return (float("-inf") if ts is None else ts, o.get("submitted_at") or "")

        rows.sort(key=sort_key)
        total = len(rows)
        page = rows[offset : offset + limit]
        items = []
        for o in page:
            issues = (o.get("trust_breakdown") or {}).get("issues", [])
            profile = self.profiles.get(o["user_id"], {})
            items.append(
                {
                    "id": o["id"],
                    "status": o["status"],
                    "trust_score": o.get("trust_score"),
                    "submitted_at": o.get("submitted_at"),
                    "lat": o.get("lat"),
                    "lng": o.get("lng"),
                    "flag_count": len(issues),
                    "citizen_display_name": profile.get("display_name"),
                }
            )
        return items, total

    def last_audit_event(self, obs_id):
        events = self.audit_events.get(obs_id) or []
        return dict(events[-1]) if events else None

    def insert_audit_event(self, row):
        key = (row["observation_id"], row["prev_hash"])
        if key in self._audit_seen:
            raise AuditConflict
        row = dict(row)
        row["id"] = self._audit_next_id
        self._audit_next_id += 1
        self._audit_seen.add(key)
        self.audit_events.setdefault(row["observation_id"], []).append(row)
        return dict(row)

    def list_audit_events(self, obs_id):
        return [dict(e) for e in self.audit_events.get(obs_id, [])]

    def upsert_lesson(self, row):
        key = (row["observation_id"], row["indicator_id"])
        lid = self._lesson_by_key.get(key)
        if lid is None:
            lid = str(self._lesson_next_id)
            self._lesson_next_id += 1
            self._lesson_by_key[key] = lid
            self.lessons[lid] = {"id": lid, "seen": False, "seen_at": None, "created_at": now_iso()}
        self.lessons[lid].update(row)
        self.lessons[lid]["id"] = lid
        return dict(self.lessons[lid])

    def list_lessons(self, user_id, unseen_only, limit):
        rows = [lesson for lesson in self.lessons.values() if lesson["user_id"] == user_id]
        if unseen_only:
            rows = [lesson for lesson in rows if not lesson["seen"]]
        rows.sort(key=lambda lesson: lesson["created_at"], reverse=True)
        return [dict(lesson) for lesson in rows[:limit]]

    def count_unseen_lessons(self, user_id):
        return sum(1 for lesson in self.lessons.values() if lesson["user_id"] == user_id and not lesson["seen"])

    def get_lesson(self, lesson_id):
        lesson = self.lessons.get(lesson_id)
        return dict(lesson) if lesson else None

    def mark_lesson_seen(self, lesson_id):
        self.lessons[lesson_id]["seen"] = True
        self.lessons[lesson_id]["seen_at"] = now_iso()
        return dict(self.lessons[lesson_id])

    def list_observations_since(self, user_id, since_iso):
        return [
            dict(o)
            for o in self.observations.values()
            if o["user_id"] == user_id and (o.get("submitted_at") or "") >= since_iso
        ]

    def list_answers_for_user(self, user_id):
        mine = {o["id"] for o in self.observations.values() if o["user_id"] == user_id}
        return [dict(a) for a in self.answers.values() if a["observation_id"] in mine]

    def list_map_observations(self, statuses):
        return [
            dict(o)
            for o in self.observations.values()
            if o["status"] in statuses and o.get("lat") is not None and o.get("lng") is not None
        ]

    def list_all_answers(self):
        return [dict(a) for a in self.answers.values()]

    def list_all_observations(self):
        return [dict(o) for o in self.observations.values()]

    # ---------------- Guardians (Phase 1) ----------------

    def add_gold_item(self, **fields):
        """Test helper: seed a gold item and get its row back."""
        row = {"id": str(uuid.uuid4()), "source": "seed", "active": True, **fields}
        self.gold_items[row["id"]] = row
        return dict(row)

    def list_gold_items(self, active_only=True):
        return [dict(g) for g in self.gold_items.values() if g.get("active", True) or not active_only]

    def get_gold_item(self, gold_id):
        g = self.gold_items.get(gold_id)
        return dict(g) if g else None

    def insert_gold_item(self, row):
        row = {"id": str(uuid.uuid4()), "created_at": now_iso(), **row}
        self.gold_items[row["id"]] = row
        return dict(row)

    def insert_vote(self, row):
        row = {"id": str(uuid.uuid4()), "created_at": now_iso(), **row}
        self.votes[row["id"]] = row
        if row.get("answer_id"):
            for answer in self.answers.values():
                if answer.get("id") == row["answer_id"]:
                    answer["crowd_votes"] = (answer.get("crowd_votes") or 0) + 1
        return dict(row)

    def get_vote(self, voter_id, answer_id=None, gold_item_id=None):
        for v in self.votes.values():
            if v["voter_id"] != voter_id:
                continue
            if answer_id and v.get("answer_id") == answer_id:
                return dict(v)
            if gold_item_id and v.get("gold_item_id") == gold_item_id:
                return dict(v)
        return None

    def update_vote(self, vote_id, fields):
        self.votes[vote_id].update(fields)
        return dict(self.votes[vote_id])

    def list_votes_for_answer(self, answer_id):
        return [dict(v) for v in self.votes.values() if v.get("answer_id") == answer_id]

    def list_votes_by_voter(self, voter_id):
        return [dict(v) for v in self.votes.values() if v["voter_id"] == voter_id]

    def list_gold_votes(self, voter_id):
        out = []
        for v in self.votes.values():
            if v["voter_id"] != voter_id or not v.get("is_gold"):
                continue
            gold = self.gold_items.get(v.get("gold_item_id")) or {}
            out.append({**v, "expert_score": gold.get("expert_score")})
        return out

    def count_votes(self, voter_id, is_gold=None):
        return sum(
            1
            for v in self.votes.values()
            if v["voter_id"] == voter_id and (is_gold is None or bool(v.get("is_gold")) == is_gold)
        )

    def list_vote_candidates(self, exclude_user_id, limit=50):
        out = []
        for a in self.answers.values():
            obs = self.observations.get(a["observation_id"]) or {}
            if obs.get("status") != "submitted" or obs.get("user_id") == exclude_user_id:
                continue
            if not a.get("photo_path") or a.get("crowd_status", "pending") != "pending":
                continue
            out.append({**a, "user_id": obs.get("user_id"), "crew_id": obs.get("crew_id")})
        out.sort(key=lambda a: a.get("crowd_votes") or 0)
        return [dict(a) for a in out[:limit]]

    def get_answer_by_id(self, answer_id):
        return next((dict(a) for a in self.answers.values() if a.get("id") == answer_id), None)

    def insert_points(self, rows):
        inserted = []
        for row in rows:
            key = (row["user_id"], row["reason"], row["ref_id"])
            if any((p["user_id"], p["reason"], p["ref_id"]) == key for p in self.points):
                continue  # unique (user_id, reason, ref_id): idempotent awarding
            saved = {"id": str(uuid.uuid4()), "created_at": now_iso(), "settled_at": None, **row}
            self.points.append(saved)
            inserted.append(dict(saved))
        return inserted

    def list_points(self, user_id, status=None):
        return [dict(p) for p in self.points if p["user_id"] == user_id and (status is None or p["status"] == status)]

    def settle_points(self, updates):
        changed = 0
        for u in updates:
            for p in self.points:
                same = (p["user_id"], p["reason"], p["ref_id"]) == (u["user_id"], u["reason"], u["ref_id"])
                if same and p["status"] == "pending":
                    p["status"] = u["status"]
                    p["settled_at"] = u["settled_at"]
                    changed += 1
        return changed

    def insert_receipt(self, row):
        row = {"id": str(uuid.uuid4()), "seen": False, "created_at": now_iso(), **row}
        self.receipts[row["id"]] = row
        return dict(row)

    def list_receipts(self, user_id, unseen_only=False, limit=20, offset=0):
        rows = [r for r in self.receipts.values() if r["user_id"] == user_id]
        if unseen_only:
            rows = [r for r in rows if not r["seen"]]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return [dict(r) for r in rows[offset : offset + limit]]

    def count_receipts(self, user_id, unseen_only=False):
        rows = [r for r in self.receipts.values() if r["user_id"] == user_id]
        if unseen_only:
            rows = [r for r in rows if not r["seen"]]
        return len(rows)

    def get_receipt(self, receipt_id):
        r = self.receipts.get(receipt_id)
        return dict(r) if r else None

    def mark_receipt_seen(self, receipt_id):
        self.receipts[receipt_id]["seen"] = True
        return dict(self.receipts[receipt_id])

    def list_user_badges(self, user_id):
        return [dict(b) for b in self.user_badges if b["user_id"] == user_id]

    def insert_user_badge(self, user_id, badge_id):
        if any(b["user_id"] == user_id and b["badge_id"] == badge_id for b in self.user_badges):
            return None
        row = {"user_id": user_id, "badge_id": badge_id, "unlocked_at": now_iso()}
        self.user_badges.append(row)
        return dict(row)

    def create_site(self, lat, lng, name):
        row = {"id": str(uuid.uuid4()), "lat": lat, "lng": lng, "name": name, "created_at": now_iso()}
        self.sites[row["id"]] = row
        return dict(row)

    def get_site(self, site_id):
        s = self.sites.get(site_id)
        return dict(s) if s else None

    def list_sites(self):
        return [dict(s) for s in self.sites.values()]

    def crew_id_for_user(self, user_id):
        return self.crews.get(user_id)

    # ---------------- Phase 6: Adopt-a-Stream ----------------

    def list_adoptions(self, user_id):
        rows = [
            a
            for a in self.adoptions.values()
            if a["user_id"] == user_id and a.get("released_at") is None
        ]
        rows.sort(key=lambda a: a["adopted_at"])
        return [{**dict(a), "site": dict(self.sites.get(a["site_id"]) or {})} for a in rows]

    def get_adoption(self, user_id, site_id):
        return next(
            (
                dict(a)
                for a in self.adoptions.values()
                if a["user_id"] == user_id and a["site_id"] == site_id and a.get("released_at") is None
            ),
            None,
        )

    def insert_adoption(self, user_id, site_id):
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "site_id": site_id,
            "adopted_at": now_iso(),
            "released_at": None,
        }
        self.adoptions[row["id"]] = row
        return dict(row)

    def release_adoption(self, adoption_id):
        self.adoptions[adoption_id]["released_at"] = now_iso()
        return dict(self.adoptions[adoption_id])

    def list_site_observations(self, site_id, user_id=None):
        rows = [
            o
            for o in self.observations.values()
            if o.get("site_id") == site_id
            and o.get("status") != "draft"
            and (user_id is None or o["user_id"] == user_id)
        ]
        rows.sort(key=lambda o: o.get("submitted_at") or "", reverse=True)
        return [dict(o) for o in rows]


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def upload(self, path, data):
        self.files[path] = data

    def signed_url(self, path):
        return f"https://signed.example/{path}" if path in self.files else None
