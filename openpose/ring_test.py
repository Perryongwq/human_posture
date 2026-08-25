"""Integration test on the real burst: find the carousel ring + its letters, and
find the gloved operator, then say which station the operator's hand is at.

Three stages, each independently reported so a failure is attributable:

  ring    classical CV, no model. Coarse hub from HoughCircles, then a 10-fold
          comb search over (hub, radius, angular offset) that locks onto the ten
          stamped bolt-head tags. The 36 deg periodicity is the fixture's own
          geometry, so this is a 3-parameter fit, not blob detection.
  letters qwen3-vl via Ollama, 4 rotations per tag, resolved by ring_fit(). Slow
          (~5 min/frame), so --vlm limits how many frames get read. The carousel
          sits at a different rotation in different frames, which is the point:
          the letters have to be re-read, not replayed from one calibration.
  human   OpenPose body pose -> wrist keypoint -> nearest station by bearing.
          Body pose, not hand landmarks: hand models score 0/91 on this white
          glove (goal.md 2026-08-21).
"""
import argparse, glob, json, os, sys, time
import cv2, numpy as np, torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ocr'))
from vlm_labels import ask, parse, rotate, ring_fit, LETTERS, ROTATIONS   # noqa: E402

RWRI, LWRI = 4, 7          # COCO-18 wrist indices
ARM_BONES = [(2, 3), (3, 4), (5, 6), (6, 7), (2, 5)]


# ───────────────────────────────────────────────────────────── ring
def _darkness_map(g, k):
    """Per-pixel 'a dark stamped mark sits in a bright cap centred here'.

    Computed once for the whole frame, so scoring any (hub, radius, angle)
    candidate later is a table lookup instead of a fresh patch reduction --
    the search evaluates ~350k candidate points and doing it the naive way
    cost ~30s/frame.

    `k` must track the bolt-cap size, so callers scale it to frame width. It was
    hardcoded at 52 for a while, which is right around 1600px wide and wrong
    everywhere else -- at 4K the window fell short of the cap, at 1920 it smeared
    across the dark inter-wedge gaps.
    """
    kern = np.ones((k, k), np.uint8)
    return cv2.boxFilter(g, -1, (k, k)) - cv2.erode(g, kern)


def _ring_pts(cx, cy, a, q, phi, offs, n):
    """Sample points of an ellipse at n evenly spaced parametric angles, for every
    candidate angular offset at once. Returns (len(offs), n) arrays of x and y.

    A tilted camera maps the fixture's circle to an ellipse, and an affine map
    keeps evenly spaced points evenly spaced in the ellipse's own parameter -- so
    the n-fold comb still applies, it just runs on an ellipse instead of a circle.
    """
    t = np.radians(offs[:, None] + (360.0 / n) * np.arange(n)[None, :])
    ct, st = np.cos(t), np.sin(t)
    cp, sp = np.cos(np.radians(phi)), np.sin(np.radians(phi))
    return (cx + a * ct * cp - a * q * st * sp,
            cy + a * ct * sp + a * q * st * cp)


def find_ring(img, n=10, r_lo=0.208, r_hi=0.232):
    """Locate the carousel hub, tag radius and the n tag positions.

    Search hub x, hub y, radius and angular offset, scoring each candidate by the
    sum of the darkness map at n points spaced 360/n apart. That aggregate is what
    makes a crude per-pixel detector reliable: noise does not have n-fold symmetry.

    `r_lo`/`r_hi` bracket the tag radius as a fraction of frame width, and they are
    load-bearing, not cosmetic. The plates' outer edge against the green floor is
    ALSO 10-fold symmetric and far higher contrast than a stamped letter, so with a
    loose range the search rails to the largest allowed radius and every tag lands
    on blank plate ~8% too far out. Measured on the reference frames the tag ring
    sits at 0.221-0.231 W. Re-measure these if the camera height changes.

    Two things that were tried here and measured WORSE -- do not re-add without
    evidence:
      * snapping each tag to the local darkness peak: the dark inter-wedge gaps
        outscore the letters, tags end up on bare plate.
      * fitting an ellipse for camera tilt: the constrained fit returns aspect
        1.00, i.e. no measurable ellipse. The apparent "sag" was mislocated tags,
        not perspective.
    """
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = img.shape[:2]
    dark = _darkness_map(g, int(0.018 * W) | 1)          # kernel tracks the bolt-cap size
    s = 0.25
    blur = cv2.medianBlur(cv2.cvtColor(cv2.resize(img, None, fx=s, fy=s), cv2.COLOR_BGR2GRAY), 5)
    c = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.5, minDist=200, param1=100,
                         param2=60, minRadius=int(0.18 * W * s), maxRadius=int(0.32 * W * s))
    cx0, cy0 = (c[0][0][0] / s, c[0][0][1] / s) if c is not None else (W / 2, H / 2)

    offs = np.arange(360.0 / n)                          # candidate angular offsets
    best = None
    for cx in np.arange(cx0 - 0.04 * W, cx0 + 0.04 * W, 0.004 * W):
        for cy in np.arange(cy0 - 0.04 * W, cy0 + 0.04 * W, 0.004 * W):
            for a in np.arange(r_lo * W, r_hi * W, 0.001 * W):
                xs, ys = _ring_pts(cx, cy, a, 1.0, 0.0, offs, n)
                comb = dark[np.clip(ys.astype(int), 0, H - 1),
                            np.clip(xs.astype(int), 0, W - 1)].sum(1)
                i = int(comb.argmax())
                if best is None or comb[i] > best[0]:
                    best = (float(comb[i]), cx, cy, a, float(offs[i]))

    v, cx, cy, a, off = best
    xs, ys = _ring_pts(cx, cy, a, 1.0, 0.0, np.array([off]), n)
    return {'hub': (cx, cy), 'radius': float(a), 'tags': list(zip(xs[0], ys[0])), 'score': v}


# ────────────────────────────────────────────────────────── letters
def read_letters(model, img, tags, half):
    """VLM-read every tag at 4 rotations, then resolve with the ring constraint."""
    reads = {}
    for k, (x, y) in enumerate(tags):
        p = cv2.resize(img[max(0, int(y - half)):int(y + half),
                           max(0, int(x - half)):int(x + half)],
                       (280, 280), interpolation=cv2.INTER_CUBIC)
        reads[k] = [parse(ask(model, rotate(p, d))) for d in ROTATIONS]
    return ring_fit({k: t for k, t in enumerate(tags)}, reads) + (reads,)


# ──────────────────────────────────────────────────────────── human
def station_of(pt, hub, tags):
    """Nearest station by bearing from the hub — the wedges are angular sectors."""
    ang = np.degrees(np.arctan2(pt[1] - hub[1], pt[0] - hub[0]))
    d = [abs((np.degrees(np.arctan2(t[1] - hub[1], t[0] - hub[0])) - ang + 180) % 360 - 180)
         for t in tags]
    return int(np.argmin(d)), min(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', default='images')
    ap.add_argument('--out', default='openpose/ring_out')
    ap.add_argument('--model', default='qwen3-vl:8b')
    ap.add_argument('--width', type=int, default=1600, help='working resolution')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--vlm', type=int, default=4, help='how many frames get letters read (slow)')
    ap.add_argument('--overlays', type=int, default=12)
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.images, '*.jpg')))[:a.limit or None]
    os.makedirs(a.out, exist_ok=True)
    vlm_idx = set(np.linspace(0, len(files) - 1, a.vlm).astype(int)) if a.vlm else set()

    from controlnet_aux.open_pose import OpenposeDetector, util
    det = OpenposeDetector.from_pretrained('lllyasviel/Annotators')
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    det.body_estimation.model.to(dev); det.body_estimation.cuda = (dev == 'cuda')
    print(f'{len(files)} images | device={dev} | width={a.width} | VLM on {len(vlm_idx)} frames',
          flush=True)

    rows, t0 = [], time.time()
    for n, f in enumerate(files):
        img = cv2.imread(f)
        sc = a.width / max(img.shape[:2])
        if sc < 1:
            img = cv2.resize(img, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        half = int(0.045 * w)

        ring = find_ring(img)
        hub, R, tags, ringscore = ring['hub'], ring['radius'], ring['tags'], ring['score']
        letters, margin = None, None
        if n in vlm_idx:
            letters, _, margin, _ = read_letters(a.model, img, tags, half)

        poses = det.detect_poses(img, include_hand=False)
        hands = []
        for p in poses:
            kp = p.body.keypoints
            for idx, side in ((RWRI, 'R'), (LWRI, 'L')):
                if idx < len(kp) and kp[idx]:
                    pt = (kp[idx].x * w, kp[idx].y * h)
                    slot, dev_deg = station_of(pt, hub, tags)
                    reach = np.hypot(pt[0] - hub[0], pt[1] - hub[1]) / R
                    hands.append({'side': side, 'xy': [round(float(v), 1) for v in pt],
                                  'slot': int(slot), 'off_deg': round(float(dev_deg), 1),
                                  'reach': round(float(reach), 2),
                                  'over_ring': bool(0.45 < reach < 1.35)})
        rows.append({'file': os.path.basename(f), 'hub': [round(float(v)) for v in hub], 'R': round(float(R)),
                     'ring_score': round(float(ringscore)), 'letters': letters, 'margin': margin,
                     'people': len(poses), 'hands': hands})

        if n < a.overlays:
            c = img.copy()
            cv2.circle(c, tuple(int(v) for v in hub), int(R), (255, 200, 0), 2)
            cv2.circle(c, tuple(int(v) for v in hub), 6, (255, 200, 0), -1)
            for k, (x, y) in enumerate(tags):
                lab = letters[k] if letters else f'#{k}'
                cv2.circle(c, (int(x), int(y)), half // 2, (0, 220, 255), 2)
                cv2.putText(c, lab, (int(x) - 14, int(y) - half // 2 - 8), 0, 1.1, (0, 220, 255), 3)
            for p in poses:
                c = util.draw_bodypose(c, p.body.keypoints)
            for hd in hands:
                x, y = int(hd['xy'][0]), int(hd['xy'][1])
                col = (0, 255, 0) if hd['over_ring'] else (120, 120, 120)
                cv2.circle(c, (x, y), 13, col, 3)
                name = letters[hd['slot']] if letters else f"#{hd['slot']}"
                txt = f"{hd['side']} wrist -> {name}" + ('' if hd['over_ring'] else ' (off ring)')
                cv2.putText(c, txt, (x + 16, y - 10), 0, 0.7, col, 2)
            cv2.imwrite(os.path.join(a.out, os.path.basename(f)[:-4] + '.png'), c)

        tag = f"letters={''.join(letters.values()) if letters else '-'} margin={margin}"
        print(f'[{n+1}/{len(files)}] {os.path.basename(f)}: hub={rows[-1]["hub"]} R={rows[-1]["R"]} '
              f'people={len(poses)} hands={len(hands)} {tag}', flush=True)

    json.dump(rows, open(os.path.join(a.out, 'results.json'), 'w'), indent=1)

    N = len(rows)
    print(f'\n=== {N} frames in {time.time()-t0:.0f}s ===')
    hubs = np.array([r['hub'] for r in rows]); Rs = np.array([r['R'] for r in rows])
    print('  ring    hub spread  x +/-%.0fpx  y +/-%.0fpx | radius %.0f +/-%.0fpx'
          % (hubs[:, 0].std(), hubs[:, 1].std(), Rs.mean(), Rs.std()))
    vl = [r for r in rows if r['letters']]
    if vl:
        print(f'  letters read on {len(vl)} frames; margins ' +
              ', '.join(str(r['margin']) for r in vl))
        for r in vl:
            print(f'    {r["file"]}: {"".join(r["letters"][k] for k in sorted(r["letters"]))} '
                  f'(margin {r["margin"]})')
    ppl = sum(r['people'] > 0 for r in rows)
    onring = sum(any(h['over_ring'] for h in r['hands']) for r in rows)
    print(f'  human   person detected {ppl}/{N} ({ppl/N:.0%}) | '
          f'wrist over the ring {onring}/{N} ({onring/N:.0%})')
    print(f'  wrote {a.out}/results.json + {min(a.overlays, N)} overlays')


if __name__ == '__main__':
    main()
