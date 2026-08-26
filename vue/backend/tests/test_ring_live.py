"""Live endpoints: /ring (geometry per frame) and /fit (letters from accumulated votes).
/read-tag is a thin wrapper over the same VLM call calibrate uses; it needs Ollama
and is exercised on the live fixture."""
import base64

import cv2

from tests.test_calibrate import READS, TAGS
from tests.test_find_ring import HUB, N, R, W, H, _fixture


def _b64(img):
    return base64.b64encode(cv2.imencode(".png", img)[1]).decode()


def test_ring_returns_normalized_geometry(client):
    r = client.post("/api/posture/ring", json={"image": _b64(_fixture()), "stations": N})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["tags"]) == N
    assert abs(d["hub"]["x"] * W - HUB[0]) < 40 and abs(d["hub"]["y"] * H - HUB[1]) < 40
    assert abs(d["radius"] * W - R) < 30
    assert all(0 <= t["x"] <= 1 and 0 <= t["y"] <= 1 for t in d["tags"])


def test_ring_rejects_garbage(client):
    assert client.post("/api/posture/ring", json={"image": "bm90IGFuIGltYWdl"}).status_code == 400


def test_fit_recovers_letters_from_noisy_votes(client):
    body = {"tags": {k: {"x": x, "y": y} for k, (x, y) in TAGS.items()}, "reads": READS}
    r = client.post("/api/posture/fit", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["letters"] == {s: s for s in TAGS}
    assert r.json()["margin"] > 0


def test_fit_rejects_mismatched_stations(client):
    body = {"tags": {k: {"x": x, "y": y} for k, (x, y) in TAGS.items()},
            "reads": {k: v for k, v in READS.items() if k != "A"}}
    assert client.post("/api/posture/fit", json=body).status_code == 400


def test_ring_locked_geometry_returns_pinned_hub_and_radius(client):
    from tests.test_find_ring import _fixture, N, HUB, R, W, H
    hub = {"x": HUB[0] / W, "y": HUB[1] / H}
    r = client.post("/api/posture/ring",
                    json={"image": _b64(_fixture()), "stations": N,
                          "hub": hub, "radius": R / W})
    assert r.status_code == 200, r.text
    d = r.json()
    # locked path must return exactly the pinned geometry, not a re-searched one
    assert abs(d["hub"]["x"] - hub["x"]) < 1e-6 and abs(d["hub"]["y"] - hub["y"]) < 1e-6
    assert abs(d["radius"] - R / W) < 1e-6
    assert len(d["tags"]) == N
