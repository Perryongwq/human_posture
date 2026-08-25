"""One image showing both detections together: the carousel ring with its letters
(classical CV + VLM) and the OpenPose body skeleton with the gloved wrist mapped to
a station.

Letters are read from a previous run's results.json rather than re-queried, because
a VLM pass costs ~4 min/frame and the answer does not change. Pass --vlm to re-read.
"""
import argparse, json, os, sys
import cv2, numpy as np, torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ring_test import find_ring, station_of, read_letters, RWRI, LWRI   # noqa: E402

# COCO-18 skeleton, drawn thicker than util.draw_bodypose so it survives downscaling
BONES = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10),
         (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
BONE_COL = (0, 140, 255)      # orange (BGR) — must not read as the cyan ring
RING_COL = (255, 200, 0)
TAG_COL = (0, 220, 255)
HAND_COL = (60, 255, 60)


def label(img, text, org, scale=0.8, col=(255, 255, 255), th=2):
    """Text with a dark outline — the fixture is white, plain text vanishes on it."""
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), th + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)


def cached_letters(out_dirs, fname):
    for d in out_dirs:
        p = os.path.join(d, 'results.json')
        if not os.path.exists(p):
            continue
        for r in json.load(open(p)):
            if r['file'] == fname and r.get('letters'):
                return {int(k): v for k, v in r['letters'].items()}, r.get('margin')
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', default='images/WIN_20260820_13_31_24_Pro.jpg')
    ap.add_argument('--out', default='openpose/combined.png')
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--model', default='qwen3-vl:8b')
    ap.add_argument('--vlm', action='store_true', help='re-read letters instead of using cache')
    a = ap.parse_args()

    img = cv2.imread(a.image)
    sc = a.width / max(img.shape[:2])
    img = cv2.resize(img, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
    h, w = img.shape[:2]
    half = int(0.045 * w)

    ring = find_ring(img)
    hub, R, tags = ring['hub'], ring['radius'], ring['tags']
    fname = os.path.basename(a.image)
    letters, margin = (None, None) if a.vlm else cached_letters(
        ['openpose/ring_letters', 'openpose/ring_out'], fname)
    if letters is None:
        letters, _, margin, _ = read_letters(a.model, img, tags, half)
    print(f'letters {"".join(letters[k] for k in sorted(letters))} margin={margin}')

    from controlnet_aux.open_pose import OpenposeDetector
    det = OpenposeDetector.from_pretrained('lllyasviel/Annotators')
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    det.body_estimation.model.to(dev); det.body_estimation.cuda = (dev == 'cuda')
    poses = det.detect_poses(img, include_hand=False)

    c = img.copy()
    # ── ring ────────────────────────────────────────────────────────
    cv2.circle(c, (int(hub[0]), int(hub[1])), int(R), RING_COL, 3, cv2.LINE_AA)
    cv2.drawMarker(c, (int(hub[0]), int(hub[1])), RING_COL, cv2.MARKER_CROSS, 34, 3)
    label(c, 'hub', (int(hub[0]) + 18, int(hub[1]) + 8), 0.7, RING_COL)
    for k, (x, y) in enumerate(tags):
        cv2.circle(c, (int(x), int(y)), half // 2, TAG_COL, 3, cv2.LINE_AA)
        label(c, letters[k], (int(x) - 16, int(y) - half // 2 - 12), 1.5, TAG_COL, 4)

    # ── skeleton ────────────────────────────────────────────────────
    hands = []
    for p in poses:
        kp = p.body.keypoints
        px = [None if (i >= len(kp) or kp[i] is None) else (int(kp[i].x * w), int(kp[i].y * h))
              for i in range(18)]
        for i, j in BONES:
            if px[i] and px[j]:
                cv2.line(c, px[i], px[j], BONE_COL, 5, cv2.LINE_AA)
        for q in px:
            if q:
                cv2.circle(c, q, 6, (255, 255, 255), -1, cv2.LINE_AA)
        for idx, side in ((RWRI, 'R'), (LWRI, 'L')):
            if px[idx]:
                slot, off = station_of(px[idx], hub, tags)
                reach = np.hypot(px[idx][0] - hub[0], px[idx][1] - hub[1]) / R
                if 0.45 < reach < 1.35:
                    hands.append((side, px[idx], letters[slot], off))

    for side, q, letter, off in hands:
        cv2.circle(c, q, 22, HAND_COL, 4, cv2.LINE_AA)
        cv2.line(c, q, (q[0] + 60, q[1] - 46), HAND_COL, 3, cv2.LINE_AA)
        label(c, f'{side} wrist  station {letter}', (q[0] + 66, q[1] - 50), 1.0, HAND_COL, 3)

    # ── legend ──────────────────────────────────────────────────────
    box = c[0:186, 0:660]
    c[0:186, 0:660] = cv2.addWeighted(box, 0.25, np.zeros_like(box), 0, 0)
    label(c, fname, (16, 34), 0.72, (255, 255, 255), 2)
    for i, (col, txt) in enumerate([
        (RING_COL, f'ring: hub + radius {R:.0f}px  (classical CV, no model)'),
        (TAG_COL, f'letters: qwen3-vl + ring fit  (margin {margin})'),
        (BONE_COL, f'OpenPose body pose: {len(poses)} person(s)'),
        (HAND_COL, f'wrist -> station: {", ".join(f"{s}={l}" for s, _, l, _ in hands) or "none"}'),
    ]):
        y = 74 + i * 30
        cv2.rectangle(c, (16, y - 12), (40, y + 4), col, -1)
        label(c, txt, (50, y), 0.62, (255, 255, 255), 1)

    cv2.imwrite(a.out, c)
    print(f'wrote {a.out}  ({w}x{h})')


if __name__ == '__main__':
    main()
