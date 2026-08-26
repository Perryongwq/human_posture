"""find_ring() — recovers hub, radius and the ten tag positions from one frame.

Synthetic fixture rather than a photo: a real frame would make this a slow,
brittle regression on JPEG contents. The geometry is what is under test.
"""
import cv2
import numpy as np

from app.routers.posture import find_ring

# R must sit inside find_ring's r_lo..r_hi bracket (fractions of width)
W, H, HUB, R, N = 1600, 900, (760.0, 470.0), 0.22 * 1600, 10


def _fixture():
    """Bright caps on a mid-grey field, each stamped with a dark mark, at 36 deg steps."""
    img = np.full((H, W, 3), 110, np.uint8)
    for k in range(N):
        a = np.radians(18 + 360 / N * k)          # deliberate non-zero offset
        x, y = int(HUB[0] + R * np.cos(a)), int(HUB[1] + R * np.sin(a))
        cv2.circle(img, (x, y), 20, (245, 245, 245), -1)   # bright cap, ~ 0.018*W
        cv2.circle(img, (x, y), 8, (25, 25, 25), -1)       # dark stamped mark
    return img


def test_recovers_hub_radius_and_every_tag():
    hub, r, tags = find_ring(_fixture(), N)
    assert len(tags) == N
    assert np.hypot(hub[0] - HUB[0], hub[1] - HUB[1]) < 40, hub
    assert abs(r - R) < 30, r
    # every true tag has a predicted tag near it, and no two share one
    truth = [(HUB[0] + R * np.cos(np.radians(18 + 36 * k)),
              HUB[1] + R * np.sin(np.radians(18 + 36 * k))) for k in range(N)]
    matched = set()
    for tx, ty in truth:
        i = min(range(N), key=lambda j: np.hypot(tags[j][0] - tx, tags[j][1] - ty))
        assert np.hypot(tags[i][0] - tx, tags[i][1] - ty) < 60
        matched.add(i)
    assert len(matched) == N, 'two stations collapsed onto the same tag'


def test_tags_are_evenly_spaced_around_the_hub():
    hub, _, tags = find_ring(_fixture(), N)
    ang = sorted(np.degrees(np.arctan2(y - hub[1], x - hub[0])) % 360 for x, y in tags)
    steps = np.diff(ang)
    assert abs(steps.mean() - 360 / N) < 1.0, steps
