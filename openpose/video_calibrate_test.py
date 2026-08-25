"""Offline mirror of the app's stage-2/5 pipeline on a raw camera video:

  calibrate once   find_ring (full search) + VLM letters + ring_fit   -- like /calibrate
  track live       find_ring with hub+radius LOCKED -> median rotation -> rotate letters
                   -- like /ring(lock) + carryLetters(). NO VLM after calibration.

Verifies the two things the app must do: the overlay follows the carousel as it
turns, and the letters stay on their physical stamps.

  python openpose/video_calibrate_test.py "video.mp4" --calib-frame 40
"""
import argparse, glob, os, sys
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'ocr'))
from vlm_labels import ask, parse, rotate, ring_fit, ROTATIONS   # noqa: E402

WIDTH = 1600


def load(cap, i, w=WIDTH):
    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
    ok, fr = cap.read()
    if not ok:
        return None
    sc = w / fr.shape[1]
    return cv2.resize(fr, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else fr


def darkness(g, k):
    return cv2.boxFilter(g, -1, (k, k)) - cv2.erode(g, np.ones((k, k), np.uint8))


def find_ring(img, n=10, r_lo=0.208, r_hi=0.232, lock=None):
    """Same as backend find_ring: full search, or offset-only when locked."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = img.shape[:2]
    dark = darkness(g, int(0.018 * W) | 1)
    if lock is not None:
        cxs, cys, Rs = [lock[0]], [lock[1]], [lock[2]]
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
    tags = [(cx + R * np.cos(np.radians(off + step * k)),
             cy + R * np.sin(np.radians(off + step * k))) for k in range(n)]
    return (cx, cy), R, tags


def bearing(pt, hub):
    return np.degrees(np.arctan2(pt[1] - hub[1], pt[0] - hub[0]))


def estimate_rotation(prev_tags, prev_hub, tags, hub, tol=8):
    """Port of liveRing.estimateRotation: median signed nearest-neighbour delta."""
    pb = [bearing(t, prev_hub) for t in prev_tags]
    deltas = []
    for t in tags:
        b = bearing(t, hub)
        best = 180.0
        for x in pb:
            s = ((b - x + 540) % 360) - 180
            if abs(s) < abs(best):
                best = s
        deltas.append(best)
    deltas.sort()
    deg = deltas[len(deltas) // 2]
    inliers = sum(abs(d - deg) <= tol for d in deltas)
    return deg, inliers


def calibrate(img, model):
    hub, R, tags = find_ring(img)
    half = int(0.045 * img.shape[1])
    reads = {}
    for k, (x, y) in enumerate(tags):
        p = cv2.resize(img[max(0, int(y - half)):int(y + half),
                           max(0, int(x - half)):int(x + half)],
                       (280, 280), interpolation=cv2.INTER_CUBIC)
        reads[k] = [parse(ask(model, rotate(p, d))) for d in ROTATIONS]
    letters, score, margin = ring_fit({k: t for k, t in enumerate(tags)}, reads)
    return hub, R, tags, letters, margin, reads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--calib-frame', type=int, default=40)
    ap.add_argument('--model', default='qwen3-vl:8b')
    ap.add_argument('--letters', default='', help='skip VLM, use these slot letters (fast render)')
    ap.add_argument('--step', type=int, default=15, help='sample every Nth frame for tracking')
    ap.add_argument('--out', default=os.path.join(HERE, 'calib_out'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cap = cv2.VideoCapture(a.video)
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    img = load(cap, a.calib_frame)
    if a.letters:
        hub0, R0, tags0 = find_ring(img)
        letters = dict(enumerate(a.letters))
        print(f'CALIBRATED @frame {a.calib_frame}: {a.letters} (VLM skipped)', flush=True)
    else:
        hub0, R0, tags0, letters, margin, reads = calibrate(img, a.model)
        print(f'CALIBRATED @frame {a.calib_frame}: {"".join(letters.values())} margin={margin}', flush=True)
        print('  per-tag reads:', {k: ''.join(v) for k, v in reads.items()}, flush=True)

    # calibrated letter map keyed to tag positions
    cal_tags = [{'x': x, 'y': y, 'letter': letters[k]} for k, (x, y) in enumerate(tags0)]
    prev_tags, prev_hub, rot = tags0, hub0, 0.0
    rows = []
    for i in range(a.calib_frame, N, a.step):
        img = load(cap, i)
        if img is None:
            break
        hub, R, tags = find_ring(img, lock=(hub0[0], hub0[1], R0))
        deg, inliers = estimate_rotation(prev_tags, prev_hub, tags, hub)
        lock_ok = inliers >= 6
        if lock_ok:
            rot += deg
            prev_tags, prev_hub = tags, hub
        rows.append((i, rot, inliers, lock_ok))
        # render overlay: rotate calibrated letters by rot about hub0
        r = np.radians(rot); c, s = np.cos(r), np.sin(r)
        vis = img.copy()
        cv2.circle(vis, tuple(int(v) for v in hub0), int(R0), (255, 0, 255), 2)
        for t in cal_tags:
            u, v = t['x'] - hub0[0], t['y'] - hub0[1]
            x, y = int(hub0[0] + u * c - v * s), int(hub0[1] + u * s + v * c)
            cv2.circle(vis, (x, y), 30, (255, 0, 255), 2)
            cv2.putText(vis, t['letter'], (x - 12, y + 12), 0, 1.1, (255, 0, 255), 3)
        cv2.putText(vis, f'f{i} rot={rot:+.0f} inliers={inliers} {"LIVE" if lock_ok else "SEARCHING"}',
                    (20, 40), 0, 1.0, (0, 255, 0) if lock_ok else (0, 165, 255), 2)
        if True:
            cv2.imwrite(os.path.join(a.out, f'f{i:04d}.jpg'), vis, [cv2.IMWRITE_JPEG_QUALITY, 80])

    cap.release()
    tot = rows[-1][1] if rows else 0
    lost = sum(not ok for _, _, _, ok in rows)
    med_in = int(np.median([r[2] for r in rows])) if rows else 0
    print(f'\n=== tracked {len(rows)} frames | total rotation {tot:+.0f}° | '
          f'median inliers {med_in}/10 | lock lost on {lost} frames ===')
    print('  rotation trace:', ' '.join(f'{r[1]:+.0f}' for r in rows[::max(1, len(rows)//20)]))
    print(f'  overlays in {a.out}')


if __name__ == '__main__':
    main()
