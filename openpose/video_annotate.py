"""Annotate a screen-recording of the fixture with OUR live pipeline:
ring (per frame), letters (VLM once, then carried by the turning ring),
and the gloved operator (OpenPose body -> wrist -> station).

The input is a screen capture of the app, so the app's own frozen overlay is
visible underneath — this render draws in magenta/green on top, letters pinned
to the physical tags, which makes divergence (the old frozen-overlay bug)
directly visible.

  python openpose/video_annotate.py "video.mp4" --calib-frame 0 --out out.mp4
"""
import argparse, os, sys, time
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'ocr'))
from ring_test import find_ring, read_letters, _darkness_map, _ring_pts   # noqa: E402

CROPW = 1600        # working width of the pane crop — same scale as the burst frames


def find_pane(frame, prev=None):
    """The app's camera pane, located by its green factory floor. Returns
    (x0, y0, x1, y1) in full-frame px, or prev if the mask is too small.
    Scroll-proof: recomputed per frame, so the pane can move in the recording."""
    hsv = cv2.cvtColor(cv2.resize(frame, None, fx=0.25, fy=0.25), cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (35, 60, 40), (90, 255, 255))
    if m.sum() < 255 * 2000:
        return prev
    ys, xs = np.nonzero(m)
    x0, x1 = xs.min() * 4, xs.max() * 4
    y0, y1 = ys.min() * 4, ys.max() * 4
    return (x0, y0, x1, min(frame.shape[0], y1 + 8))


def crop_pane(frame, pane):
    x0, y0, x1, y1 = pane
    sc = CROPW / (x1 - x0)
    crop = cv2.resize(frame[y0:y1, x0:x1], (CROPW, int((y1 - y0) * sc)))
    return crop, (x0, y0, sc)


def warm_ring(img, prev):
    """find_ring's comb search, tightly bracketed around the previous fit."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = img.shape[:2]
    dark = _darkness_map(g, int(0.018 * W) | 1)
    (pcx, pcy), pa = prev['hub'], prev['radius']
    offs = np.arange(0, 36.0, 0.5)
    best = None
    for cx in np.arange(pcx - 0.012 * W, pcx + 0.013 * W, 0.004 * W):
        for cy in np.arange(pcy - 0.012 * W, pcy + 0.013 * W, 0.004 * W):
            for a in np.arange(pa - 0.003 * W, pa + 0.0031 * W, 0.001 * W):
                xs, ys = _ring_pts(cx, cy, a, 1.0, 0.0, offs, 10)
                comb = dark[np.clip(ys.astype(int), 0, H - 1),
                            np.clip(xs.astype(int), 0, W - 1)].sum(1)
                i = int(comb.argmax())
                if best is None or comb[i] > best[0]:
                    best = (float(comb[i]), cx, cy, a, float(offs[i]))
    v, cx, cy, a, off = best
    xs, ys = _ring_pts(cx, cy, a, 1.0, 0.0, np.array([off]), 10)
    return {'hub': (cx, cy), 'radius': float(a), 'tags': list(zip(xs[0], ys[0])), 'score': v}


def bearing(pt, hub):
    return float(np.degrees(np.arctan2(pt[1] - hub[1], pt[0] - hub[0]))) % 360


def inherit_letters(ring, prev_ring, prev_letters):
    """Give each new tag the letter of the nearest previous tag by bearing.
    Returns (letters, median rotation step in deg)."""
    letters, deltas = {}, []
    pb = [bearing(t, prev_ring['hub']) for t in prev_ring['tags']]
    for k, t in enumerate(ring['tags']):
        b = bearing(t, ring['hub'])
        d = [abs((b - x + 180) % 360 - 180) for x in pb]
        j = int(np.argmin(d))
        letters[k] = prev_letters[j]
        deltas.append((b - pb[j] + 180) % 360 - 180)
    return letters, float(np.median(deltas))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--out', default='')
    ap.add_argument('--calib-frame', type=int, default=0)
    ap.add_argument('--model', default='qwen3-vl:8b')
    ap.add_argument('--letters', default='', help='skip VLM, seed slot letters e.g. IHGFEDCBAJ')
    ap.add_argument('--step', type=int, default=2, help='process every Nth frame')
    ap.add_argument('--pose-every', type=int, default=2, help='pose every Nth processed frame')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    import torch
    from controlnet_aux.open_pose import OpenposeDetector, util
    det = OpenposeDetector.from_pretrained('lllyasviel/Annotators')
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    det.body_estimation.model.to(dev); det.body_estimation.cuda = (dev == 'cuda')

    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W, H = int(cap.get(3)), int(cap.get(4))
    out_path = a.out or os.path.splitext(a.video)[0] + '_annotated.mp4'
    wr = None
    for fourcc in ('avc1', 'mp4v'):
        wr = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*fourcc), fps / a.step, (W, H))
        if wr.isOpened():
            print('codec', fourcc, flush=True)
            break
    RWRI, LWRI = 4, 7

    pane = ring = letters = cal_bearing = None
    rot = 0.0
    poses = []
    n_proc = 0
    t0 = time.time()
    for i in range(N if not a.limit else a.limit):
        ok, frame = cap.read()
        if not ok:
            break
        if i % a.step:
            continue
        if i < a.calib_frame:
            wr.write(frame)
            continue
        pane = find_pane(frame, pane)
        if pane is None:
            wr.write(frame)
            continue
        crop, (x0, y0, sc) = crop_pane(frame, pane)

        if ring is None:
            ring = find_ring(crop)
        else:
            prev = ring
            ring = warm_ring(crop, prev)
            if letters:
                letters, _ = inherit_letters(ring, prev, letters)
                # absolute rotation: mean bearing delta of every letter vs calibration
                ds = [(bearing(ring['tags'][k], ring['hub']) - cal_bearing[L] + 180) % 360 - 180
                      for k, L in letters.items()]
                rot = float(np.median(ds))

        if letters is None and i >= a.calib_frame:
            if a.letters:
                letters = dict(enumerate(a.letters))
                margin = None
            else:
                letters, _, margin, _ = read_letters(a.model, crop, ring['tags'],
                                                     int(0.045 * CROPW))
            print(f'calibrated at frame {i}: '
                  f'{"".join(letters.values()) if letters else "FAILED"} margin={margin}',
                  flush=True)
            if not letters:
                sys.exit('ring_fit margin too low - pass --letters to seed manually')
            cal_bearing = {L: bearing(ring['tags'][k], ring['hub'])
                           for k, L in letters.items()}

        if n_proc % a.pose_every == 0:
            poses = det.detect_poses(crop, include_hand=False)
        n_proc += 1

        # ── draw: crop coords -> full frame via /sc + origin ──
        def full(px, py):
            return int(px / sc + x0), int(py / sc + y0)
        hub, R = ring['hub'], ring['radius']
        cv2.circle(frame, full(*hub), int(R / sc), (255, 0, 255), 2)
        cv2.circle(frame, full(*hub), 5, (255, 0, 255), -1)
        half = int(0.0225 * CROPW)
        for k, (x, y) in enumerate(ring['tags']):
            cv2.circle(frame, full(x, y), int(half / sc), (255, 0, 255), 2)
            if letters:
                lx, ly = full(x, y)
                cv2.putText(frame, letters[k], (lx - 12, ly + 12), 0, 1.1, (255, 0, 255), 3)
        hands = []
        for p in poses:
            kp = p.body.keypoints
            for idx, side in ((RWRI, 'R'), (LWRI, 'L')):
                if idx < len(kp) and kp[idx]:
                    px, py = kp[idx].x * CROPW, kp[idx].y * crop.shape[0]
                    reach = np.hypot(px - hub[0], py - hub[1]) / R
                    b = bearing((px, py), hub)
                    slot = min(range(10), key=lambda k:
                               abs((bearing(ring['tags'][k], hub) - b + 180) % 360 - 180))
                    over = 0.45 < reach < 1.35
                    fx, fy = full(px, py)
                    col = (0, 255, 0) if over else (140, 140, 140)
                    cv2.circle(frame, (fx, fy), 12, col, 3)
                    if letters:
                        txt = f"{side} -> {letters[slot]}" + ('' if over else ' (off)')
                        cv2.putText(frame, txt, (fx + 15, fy - 10), 0, 0.8, col, 2)
                    hands.append(letters[slot] if over and letters else None)
        hud = f"OUR PIPELINE  rot {rot:+.1f} deg  ring r={int(R / sc)}px"
        cv2.putText(frame, hud, (x0 + 10, max(30, y0 + 30)), 0, 0.9, (255, 0, 255), 2)
        wr.write(frame)
        if n_proc % 100 == 0:
            print(f'{i}/{N} rot={rot:+.1f} active={[h for h in hands if h]} '
                  f'{time.time() - t0:.0f}s', flush=True)

    wr.release()
    print(f'wrote {out_path} ({n_proc} frames, {time.time() - t0:.0f}s)')


if __name__ == '__main__':
    main()
