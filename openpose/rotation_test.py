"""Does the letter mapping turn WITH the carousel?

Two phases, run separately because phase B is slow (VLM ~4 min/frame):

  A  (fast)  motion timeline: fraction of changed pixels in the tag-ring annulus
             between consecutive frames. The camera is fixed, so a stationary
             carousel diffs to ~0; a rotating one lights up the whole annulus,
             while an operator hand only lights up one sector. Prints the
             stationary segments.
  B  (slow)  --vlm i,j,k...  ring + VLM letters on the chosen frames, then for
             every frame the absolute bearing (deg from hub) of each letter.
             PASS iff (1) within a segment each letter sits at the same bearing,
             and (2) across segments every letter moved by the SAME delta -- a
             rigid rotation, i.e. ring and letters turned together.

Usage:
  python openpose/rotation_test.py                    # phase A
  python openpose/rotation_test.py --vlm 0,16,25,...  # phase B
  python openpose/rotation_test.py --report           # compare saved phase-B reads
"""
import argparse, glob, json, os, sys
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'ocr'))

OUT = os.path.join(HERE, 'rotation_out')
WIDTH = 1600


def load(f):
    img = cv2.imread(f)
    sc = WIDTH / max(img.shape[:2])
    return cv2.resize(img, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else img


def motion_timeline(files):
    """Fraction of annulus pixels changed between consecutive frames."""
    hub, R = (700, 460), 376        # camera is fixed; measured means over the burst
    prev, rows = None, []
    mask = None
    for f in files:
        g = cv2.cvtColor(load(f), cv2.COLOR_BGR2GRAY)
        if mask is None:
            yy, xx = np.mgrid[:g.shape[0], :g.shape[1]]
            r = np.hypot(xx - hub[0], yy - hub[1])
            mask = (r > 0.80 * R) & (r < 1.15 * R)
        if prev is not None:
            d = cv2.absdiff(g, prev)
            rows.append(float((d[mask] > 20).mean()))
        prev = g
    return rows


def phase_a(files):
    tl = motion_timeline(files)
    print('frame-to-frame changed fraction of the tag-ring annulus:')
    segs, start = [], 0
    for i, v in enumerate(tl):
        moving = v > 0.30          # rotation lights up the whole annulus
        print(f'  {i:2d}->{i+1:2d}  {v:.3f} {"ROTATION" if moving else ""}'
              f'  ({os.path.basename(files[i+1])})')
        if moving:
            segs.append((start, i)); start = i + 1
    segs.append((start, len(files) - 1))
    print('\nstationary segments (frame index ranges):')
    for s in segs:
        print(f'  {s[0]}..{s[1]}')
    json.dump({'timeline': tl, 'segments': segs},
              open(os.path.join(OUT, 'motion.json'), 'w'), indent=1)


def phase_b(files, idxs, model):
    from ring_test import find_ring, read_letters
    out = {}
    if os.path.exists(os.path.join(OUT, 'letters.json')):
        out = json.load(open(os.path.join(OUT, 'letters.json')))
    for i in idxs:
        img = load(files[i])
        ring = find_ring(img)
        letters, _, margin, reads = read_letters(model, img, ring['tags'], int(0.045 * img.shape[1]))
        hub = ring['hub']
        bear = {}
        if letters:
            for k, (x, y) in enumerate(ring['tags']):
                bear[letters[k]] = round(float(np.degrees(np.arctan2(y - hub[1], x - hub[0]))) % 360, 1)
        out[str(i)] = {'file': os.path.basename(files[i]), 'hub': [round(v) for v in hub],
                       'R': round(ring['radius']), 'margin': margin,
                       'letters': ''.join(letters.values()) if letters else None,
                       'bearings': bear,
                       'raw': {str(k): v for k, v in reads.items()}}
        json.dump(out, open(os.path.join(OUT, 'letters.json'), 'w'), indent=1)
        print(f'[{i}] {out[str(i)]["file"]}: {out[str(i)]["letters"]} margin={margin} '
              f'bearings={bear}', flush=True)


def report():
    data = json.load(open(os.path.join(OUT, 'letters.json')))
    segs = json.load(open(os.path.join(OUT, 'motion.json')))['segments']
    seg_of = lambda i: next(n for n, (a, b) in enumerate(segs) if a <= i <= b)
    frames = sorted(data.items(), key=lambda kv: int(kv[0]))
    ok = True

    print('per-frame letter bearings (deg from hub, screen coords):')
    for i, d in frames:
        print(f'  seg{seg_of(int(i))} [{i}] {d["file"]}: {d["letters"]} margin={d["margin"]}')

    print('\nwithin-segment consistency (same letter, same bearing):')
    by_seg = {}
    for i, d in frames:
        by_seg.setdefault(seg_of(int(i)), []).append(d)
    for s, ds in sorted(by_seg.items()):
        ref = ds[0]['bearings']
        for d in ds[1:]:
            errs = [abs((d['bearings'][L] - ref[L] + 180) % 360 - 180) for L in ref if L in d['bearings']]
            worst = max(errs) if errs else 999
            same = d['letters'] == ds[0]['letters'] or sorted(d['letters']) == sorted(ds[0]['letters'])
            flag = 'OK' if worst < 6 and same else 'FAIL'
            ok &= flag == 'OK'
            print(f'  seg{s}: {ds[0]["file"]} vs {d["file"]}: max bearing diff {worst:.1f} deg [{flag}]')

    print('\nacross-segment rigid rotation (every letter must move by the same delta):')
    seg_ref = {s: ds[0] for s, ds in by_seg.items()}
    ss = sorted(seg_ref)
    for a, b in zip(ss, ss[1:]):
        da, db = seg_ref[a]['bearings'], seg_ref[b]['bearings']
        deltas = sorted(((db[L] - da[L] + 180) % 360 - 180) for L in da if L in db)
        spread = deltas[-1] - deltas[0]
        med = deltas[len(deltas) // 2]
        flag = 'OK' if spread < 8 else 'FAIL'
        ok &= flag == 'OK'
        print(f'  seg{a} -> seg{b}: rotation {med:+.1f} deg (= {med/36.1:+.2f} stations), '
              f'per-letter spread {spread:.1f} deg [{flag}]')

    print(f'\n=== {"PASS: ring and letters turn together" if ok else "FAIL"} ===')
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', default=os.path.join(os.path.dirname(HERE), 'images'))
    ap.add_argument('--vlm', default='', help='comma-separated frame indices for letter reading')
    ap.add_argument('--model', default='qwen3-vl:8b')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(a.images, '*.jpg')))
    if a.report:
        sys.exit(0 if report() else 1)
    elif a.vlm:
        phase_b(files, [int(v) for v in a.vlm.split(',')], a.model)
    else:
        phase_a(files)


if __name__ == '__main__':
    main()
