"""Tamper-evident audit log: a SHA-256 hash chain, no blockchain.

Each event's hash covers the previous event's hash plus this event's own
canonical JSON, so altering any past event (or its position) breaks every
hash after it. verify_chain() recomputes the chain to detect that.
"""

import hashlib
import json

from app.services.db import AuditConflict, RepoProtocol, now_iso

GENESIS = "0" * 64


def _canonical(observation_id: str, actor_id: str | None, event: str, payload: dict) -> str:
    return json.dumps(
        {"observation_id": observation_id, "actor_id": actor_id, "event": event, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def compute_hash(prev_hash: str, observation_id: str, actor_id: str | None, event: str, payload: dict) -> str:
    body = prev_hash + _canonical(observation_id, actor_id, event, payload)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def append_event(
    repo: RepoProtocol,
    observation_id: str,
    actor_id: str | None,
    event: str,
    payload: dict | None = None,
) -> dict:
    payload = dict(payload or {})
    created_at = now_iso()
    # Timestamp lives INSIDE the hashed payload: Postgres timestamptz reformats on
    # round-trip (Z vs +00:00, microseconds), which would break verification. jsonb
    # keeps the string exactly as written.
    payload["ts"] = created_at

    for attempt in range(2):  # one retry on a prev_hash race
        last = repo.last_audit_event(observation_id)
        prev_hash = last["hash"] if last else GENESIS
        h = compute_hash(prev_hash, observation_id, actor_id, event, payload)
        row = {
            "observation_id": observation_id,
            "actor_id": actor_id,
            "event": event,
            "payload": payload,
            "prev_hash": prev_hash,
            "hash": h,
            "created_at": created_at,
        }
        try:
            return repo.insert_audit_event(row)
        except AuditConflict:
            if attempt == 1:
                raise
            continue
    raise AuditConflict  # pragma: no cover


def verify_chain(events: list[dict]) -> dict:
    """events must be ordered by id ascending."""
    prev = GENESIS
    for i, e in enumerate(events):
        expected = compute_hash(prev, e["observation_id"], e.get("actor_id"), e["event"], e["payload"])
        if e.get("prev_hash") != prev or e.get("hash") != expected:
            return {"valid": False, "broken_at": i, "count": len(events)}
        prev = e["hash"]
    return {"valid": True, "broken_at": None, "count": len(events)}
