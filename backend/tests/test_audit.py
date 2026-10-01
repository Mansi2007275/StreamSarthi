import json

from app.services import audit
from app.services.db import AuditConflict
from tests.fakes import FakeRepo


def test_appended_events_verify_valid():
    repo = FakeRepo()
    for i in range(3):
        audit.append_event(repo, "obs-1", "actor-1", f"event{i}", {"n": i})
    events = repo.list_audit_events("obs-1")
    assert audit.verify_chain(events) == {"valid": True, "broken_at": None, "count": 3}


def test_mutated_payload_breaks_chain_at_that_index():
    repo = FakeRepo()
    for i in range(3):
        audit.append_event(repo, "obs-1", "actor-1", f"event{i}", {"n": i})
    events = repo.list_audit_events("obs-1")
    events[1]["payload"] = {"n": 999}
    result = audit.verify_chain(events)
    assert result["valid"] is False
    assert result["broken_at"] == 1


def test_changed_prev_hash_breaks_chain():
    repo = FakeRepo()
    for i in range(3):
        audit.append_event(repo, "obs-1", "actor-1", f"event{i}", {"n": i})
    events = repo.list_audit_events("obs-1")
    events[2]["prev_hash"] = "f" * 64
    result = audit.verify_chain(events)
    assert result["valid"] is False
    assert result["broken_at"] == 2


def test_race_on_prev_hash_retries_once_and_stays_valid(monkeypatch):
    repo = FakeRepo()
    audit.append_event(repo, "obs-1", "actor-1", "first", {})

    real_insert = repo.insert_audit_event
    calls = {"n": 0}

    def flaky_insert(row):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AuditConflict
        return real_insert(row)

    monkeypatch.setattr(repo, "insert_audit_event", flaky_insert)
    audit.append_event(repo, "obs-1", "actor-1", "second", {})

    events = repo.list_audit_events("obs-1")
    assert len(events) == 2
    assert audit.verify_chain(events)["valid"] is True
    assert calls["n"] == 2


def test_payloads_never_contain_an_email():
    repo = FakeRepo()
    audit.append_event(repo, "obs-1", "actor-1", "observation_created", {"lat": 1.0, "lng": 2.0})
    audit.append_event(
        repo, "obs-1", "actor-1", "ai_suggested", {"indicator": "water_colour", "ai_score": 3, "confidence": 0.8}
    )
    events = repo.list_audit_events("obs-1")
    for e in events:
        assert "@" not in json.dumps(e["payload"])
