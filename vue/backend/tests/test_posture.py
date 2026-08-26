# backend/tests/test_posture.py
"""Posture session save/list round-trip."""
import json


def test_posture_session_roundtrip(client, tmp_path, monkeypatch):
    from app.routers import posture
    monkeypatch.setattr(posture, "DATA_FILE", tmp_path / "sessions.json")

    body = {
        "started_at": "2026-07-12T08:00:00Z",
        "ended_at": "2026-07-12T08:10:00Z",
        "place_count": 7,
        "left_count": 3,
        "right_count": 4,
        "settings": {"gripThreshold": 0.35},
    }
    r = client.post("/api/posture/sessions", json=body)
    assert r.status_code == 200
    saved = r.json()
    assert saved["place_count"] == 7
    assert saved["payroll"] == "T001"  # from mock JWT, not client-supplied
    assert saved["id"]

    r = client.get("/api/posture/sessions")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == saved["id"]


def test_posture_rejects_negative_count(client, tmp_path, monkeypatch):
    from app.routers import posture
    monkeypatch.setattr(posture, "DATA_FILE", tmp_path / "sessions.json")

    r = client.post("/api/posture/sessions", json={
        "started_at": "2026-07-12T08:00:00Z",
        "ended_at": "2026-07-12T08:10:00Z",
        "place_count": -1,
    })
    assert r.status_code == 422
