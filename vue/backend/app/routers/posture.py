# backend/app/routers/posture.py
"""
Carousel station tracking — session persistence + one-shot fixture calibration.

Counting happens entirely in the browser; this router stores finished-session
summaries, and calibrates the fixture (ring geometry + station letters) on demand.
"""
import base64
import json
import math
import threading
import uuid
from pathlib import Path

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.models import JWTClaims

router = APIRouter(prefix="/api/posture", tags=["posture"])

# ponytail: JSON-file store, single-process. Swap to DB (MCP/queue insert)
# when sessions need to survive redeploys or serve multiple workers.
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "posture_sessions.json"
_lock = threading.Lock()


class PostureSession(BaseModel):
    started_at: str            # ISO 8601
    ended_at: str              # ISO 8601
    place_count: int = Field(ge=0)
    left_count: int = Field(0, ge=0)
    right_count: int = Field(0, ge=0)
    settings: dict = {}        # calibration + thresholds used, for reproducibility


def _read_all() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@router.post("/sessions")
def save_session(body: PostureSession, user: JWTClaims = Depends(get_current_user)):
    record = {"id": str(uuid.uuid4()), "payroll": user.payroll, **body.model_dump()}
    with _lock:
        sessions = _read_all()
        sessions.append(record)
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps(sessions, indent=1), encoding="utf-8")
    return record


@router.get("/sessions")
def list_sessions(user: JWTClaims = Depends(get_current_user)):
    with _lock:
        sessions = _read_all()
    return sorted(sessions, key=lambda s: s["started_at"], reverse=True)


# ═══════════════════════════════════════════════════════════════════
# Carousel calibration — ring + letters. One call, run once per stop.
#
# Nothing rotates while an operator works the fixture, so the ring geometry and
# the letter on each station hold for the whole interaction. That is why a ~4 min
# VLM pass is affordable here and per-frame OCR never was.
#
# Measured on the 91-frame reference burst (see goal.md):
#   ring     radius 375 +/- 5px (1.4%) across 91 frames, 0.03 s/frame
#   letters  Tesseract 0/10 | VLM alone 4-5/10 | VLM + ring fit 10/10
# ═══════════════════════════════════════════════════════════════════
LETTERS = "ABCDEFGHIJ"
ROTATIONS = (0, 90, 180, 270)
CROP_PX = 280          # upscale target: at native ~15px the stamped letter is unreadable


class CalibrateRequest(BaseModel):
    image: str                                  # base64 JPEG/PNG of one calibration frame
    stations: int = Field(10, ge=3, le=26)
    crop: float = Field(0.045, gt=0, lt=0.2)    # tag crop half-size, fraction of frame width


# ───────────────────────────────────────────────────────────── ring
def _darkness(g, k):
    """Per-pixel 'a dark stamped mark sits in a bright cap centred here'.

    Precomputed for the whole frame so scoring a candidate is a table lookup.
    Recomputing patch statistics per candidate instead cost ~30 s/frame for an
    identical fit. `k` tracks the bolt-cap size, so callers scale it to the frame.
    """
    return cv2.boxFilter(g, -1, (k, k)) - cv2.erode(g, np.ones((k, k), np.uint8))


def find_ring(img, n=10, r_lo=0.208, r_hi=0.232, lock=None):
    """Locate the carousel hub, tag radius and the n tag positions, in pixels.

    Coarse hub from HoughCircles, then a comb search over (hub x, hub y, radius,
    angular offset), scoring each candidate by the darkness map summed at n points
    spaced 360/n apart. That aggregate is what makes a crude per-pixel detector
    reliable: noise does not have n-fold symmetry.

    `r_lo`/`r_hi` bracket the tag radius as a fraction of frame width and are
    load-bearing, not cosmetic. The plates' outer edge against the green floor is
    ALSO 10-fold symmetric and far higher contrast than a stamped letter, so with a
    loose range the search rails to the largest allowed radius and every tag lands
    on blank plate ~8% too far out. Measured on the reference frames the tag ring
    sits at 0.221-0.231 W. Re-measure if the camera height changes.

    Tried and measured WORSE -- do not re-add without evidence: snapping tags to the
    local darkness peak (the dark inter-wedge gaps outscore the letters), and fitting
    an ellipse for camera tilt (constrained fit returns aspect 1.00; the apparent
    "sag" was mislocated tags, not perspective).
    """
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = img.shape[:2]
    dark = _darkness(g, int(0.018 * W) | 1)

    if lock is not None:
        # Camera + fixture are fixed; only the carousel rotates. Pin hub+radius from
        # calibration and sweep just the angular offset -- re-searching hub/radius on a
        # body-cluttered live frame jitters the geometry and stalls the overlay.
        cxs, cys, Rs = [lock["hub"][0]], [lock["hub"][1]], [lock["radius"]]
    else:
        s = 0.25
        blur = cv2.medianBlur(cv2.cvtColor(cv2.resize(img, None, fx=s, fy=s), cv2.COLOR_BGR2GRAY), 5)
        c = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.5, minDist=200, param1=100,
                             param2=60, minRadius=int(0.18 * W * s), maxRadius=int(0.32 * W * s))
        cx0, cy0 = (c[0][0][0] / s, c[0][0][1] / s) if c is not None else (W / 2, H / 2)
        cxs = np.arange(cx0 - 0.04 * W, cx0 + 0.04 * W, 0.004 * W)
        cys = np.arange(cy0 - 0.04 * W, cy0 + 0.04 * W, 0.004 * W)
        Rs = np.arange(r_lo * W, r_hi * W, 0.001 * W)

    step = 360.0 / n
    offs = np.arange(step)
    ang = np.radians(offs[:, None] + step * np.arange(n)[None, :])
    ca, sa = np.cos(ang), np.sin(ang)
    best = None
    for cx in cxs:
        for cy in cys:
            for R in Rs:
                xs = np.clip((cx + R * ca).astype(int), 0, W - 1)
                ys = np.clip((cy + R * sa).astype(int), 0, H - 1)
                comb = dark[ys, xs].sum(1)
                i = int(comb.argmax())
                if best is None or comb[i] > best[0]:
                    best = (float(comb[i]), cx, cy, R, float(offs[i]))
    _, cx, cy, R, off = best
    tags = [(cx + R * math.cos(math.radians(off + step * k)),
             cy + R * math.sin(math.radians(off + step * k))) for k in range(n)]
    return (cx, cy), R, tags


# ────────────────────────────────────────────────────────── letters
PROMPT = (
    "This image shows a single capital letter stamped on a round metal bolt head. "
    "The letter may be dirty, worn, or upside down. "
    f"It is one of these ten: {', '.join(LETTERS)}. "
    "Answer with that one letter only."
)


def _parse_letter(text: str) -> str:
    """First A-J character in the reply, or '?'. VLMs pad with prose however
    firmly you ask them not to."""
    for ch in (text or "").upper():
        if ch in LETTERS:
            return ch
    return "?"


def ring_fit(tags: dict, reads: dict) -> tuple[dict, int, int]:
    """Assign letters to stations using the fixture's geometry, not just the OCR.

    The stations sit in strict alphabetical order around the hub at even angular
    steps (measured: 36.1 deg mean, 34-39 spread). That leaves only 2N candidate
    assignments -- N rotational offsets x 2 directions -- so letters need only be
    read *mostly* right. Scoring each candidate against the raw votes recovers
    stations the model never read correctly at all.

    Returns (assignment, score, margin). Margin is the vote gap to the runner-up:
    low margin means the reads were too noisy to trust.
    """
    keys = list(tags)
    cx = sum(tags[k][0] for k in keys) / len(keys)
    cy = sum(tags[k][1] for k in keys) / len(keys)
    ring = sorted(keys, key=lambda k: math.atan2(tags[k][1] - cy, tags[k][0] - cx) % (2 * math.pi))
    n = len(ring)
    scored = sorted(
        (
            (sum(reads[s].count(g[s]) for s in ring), g)
            for direction in (1, -1)
            for off in range(n)
            for g in ({ring[i]: LETTERS[(off + direction * i) % n] for i in range(n)},)
        ),
        key=lambda t: -t[0],
    )
    return scored[0][1], scored[0][0], scored[0][0] - scored[1][0]


def _rotate(patch, deg):
    if deg % 360 == 0:
        return patch
    m = cv2.getRotationMatrix2D((CROP_PX / 2, CROP_PX / 2), deg, 1.0)
    return cv2.warpAffine(patch, m, (CROP_PX, CROP_PX), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


async def _read_tags(client, img, tags, half):
    """VLM-read every tag at 4 rotations. A single fixed rotation only manages
    4-5/10 because the stations are radial, so each letter sits at its own angle."""
    reads, (H, W) = {}, img.shape[:2]
    for k, (x, y) in enumerate(tags):
        y0, y1 = max(0, int(y - half)), min(H, int(y + half))
        x0, x1 = max(0, int(x - half)), min(W, int(x + half))
        if y1 - y0 < 8 or x1 - x0 < 8:
            reads[k] = ["?"] * len(ROTATIONS)      # tag fell outside the frame
            continue
        patch = cv2.resize(img[y0:y1, x0:x1], (CROP_PX, CROP_PX), interpolation=cv2.INTER_CUBIC)
        votes = []
        for d in ROTATIONS:
            png = base64.b64encode(cv2.imencode(".png", _rotate(patch, d))[1]).decode()
            try:
                r = await client.post(
                    f"{settings.OLLAMA_URL}/api/generate",
                    json={"model": settings.OLLAMA_VISION_MODEL, "prompt": PROMPT,
                          "images": [png], "stream": False, "think": False,
                          # qwen3-vl emits a hidden reasoning block before the letter, so
                          # the cap must clear it: num_predict 8 truncated to an empty reply,
                          # 384 clears every real block while killing the ~2900-token runaways
                          # that made some reads take ~28 s (measured 2026-08-25).
                          "options": {"temperature": 0, "num_predict": 384}},
                )
                r.raise_for_status()
                votes.append(_parse_letter(r.json().get("response", "")))
            except Exception:
                votes.append("?")      # a dead model must not sink the whole read
        reads[k] = votes
    return reads


def _decode(b64: str):
    raw = np.frombuffer(base64.b64decode(b64), np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "could not decode the frame")
    return img


@router.post("/calibrate")
async def calibrate(body: CalibrateRequest, user: JWTClaims = Depends(get_current_user)):
    """Find the ring and read its station letters from one frame.

    Everything is returned normalized to [0,1] so the browser can scale it to any
    canvas size. `margin` is the caller's trust signal -- apply the letters only
    when it is comfortably above zero.
    """
    img = _decode(body.image)
    H, W = img.shape[:2]

    hub, R, tags = find_ring(img, body.stations)
    async with httpx.AsyncClient(timeout=300) as client:
        reads = await _read_tags(client, img, tags, int(body.crop * W))
    letters, score, margin = ring_fit(dict(enumerate(tags)), reads)

    return {
        "hub": {"x": hub[0] / W, "y": hub[1] / H},
        "radius": R / W,                       # normalized to width, as x is
        "tags": [{"x": x / W, "y": y / H, "letter": letters[k]}
                 for k, (x, y) in enumerate(tags)],
        "margin": margin, "score": score,
        "reads": {str(k): v for k, v in reads.items()},
        "model": settings.OLLAMA_VISION_MODEL,
    }


# ═══════════════════════════════════════════════════════════════════
# Live ring + rolling letter verification. The one-shot calibrate above
# memorises geometry that the carousel then rotates away from; these let the
# browser re-detect the ring from the actual image a few times a second and
# re-verify one tag at a time in the background, so nothing is dead-reckoned.
# ═══════════════════════════════════════════════════════════════════
class RingRequest(BaseModel):
    image: str                                  # base64 JPEG, downscaled is fine (>= ~900px wide)
    stations: int = Field(10, ge=3, le=26)
    hub: dict | None = None                      # {x,y} normalized: lock geometry, track rotation only
    radius: float | None = None                  # normalized to width


@router.post("/ring")
def ring(body: RingRequest, user: JWTClaims = Depends(get_current_user)):
    """Ring geometry only, no letters. ~0.03 s — cheap enough to call at a few Hz.

    Pass calibration `hub`+`radius` to LOCK the geometry and sweep only the angular
    offset: the camera and fixture are fixed, so re-searching them on a cluttered live
    frame just makes the overlay jitter and stall."""
    img = _decode(body.image)
    H, W = img.shape[:2]
    lock = None
    if body.hub is not None and body.radius is not None:
        lock = {"hub": (body.hub["x"] * W, body.hub["y"] * H), "radius": body.radius * W}
    hub, R, tags = find_ring(img, body.stations, lock=lock)
    return {"hub": {"x": hub[0] / W, "y": hub[1] / H}, "radius": R / W,
            "tags": [{"x": x / W, "y": y / H} for x, y in tags]}


class ReadTagRequest(BaseModel):
    image: str
    x: float = Field(ge=0, le=1)                # tag centre, normalized
    y: float = Field(ge=0, le=1)
    crop: float = Field(0.045, gt=0, lt=0.2)


@router.post("/read-tag")
async def read_tag(body: ReadTagRequest, user: JWTClaims = Depends(get_current_user)):
    """The 4-rotation VLM votes for ONE tag (1-30 s). The browser cycles through
    the tags and feeds the votes to /fit."""
    img = _decode(body.image)
    H, W = img.shape[:2]
    async with httpx.AsyncClient(timeout=300) as client:
        reads = await _read_tags(client, img, [(body.x * W, body.y * H)], int(body.crop * W))
    return {"votes": reads[0], "model": settings.OLLAMA_VISION_MODEL}


class FitRequest(BaseModel):
    tags: dict[str, dict]                       # key -> {x, y}; key is whatever the caller uses
    reads: dict[str, list[str]]                 # key -> accumulated votes


@router.post("/fit")
def fit(body: FitRequest, user: JWTClaims = Depends(get_current_user)):
    """Alphabetical ring fit over accumulated votes. Same trust rule as calibrate:
    apply only when `margin` is comfortably above zero."""
    if len(body.tags) < 3 or set(body.tags) != set(body.reads):
        raise HTTPException(400, "tags and reads must cover the same stations")
    letters, score, margin = ring_fit({k: (v["x"], v["y"]) for k, v in body.tags.items()},
                                      body.reads)
    return {"letters": letters, "score": score, "margin": margin}
