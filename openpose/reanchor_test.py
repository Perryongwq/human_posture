"""Validate the slip re-anchor (liveRing.stationOffset/snapCal) on a RAW frame.

The screen-recordings that show the bug have the overlay burned in, so find_ring
can't read them; the app's re-anchor uses the raw camera frame, so we test on
that. Two conditions, mirroring the two videos:
  slipped  labels +1 station ahead (the 'stability' failure) -> must detect n=1, snap back
  aligned  labels correct        (the 'success' case)         -> must detect n=0, no change

  python openpose/reanchor_test.py "raw.mp4" --frame 40 --letters IHGFEDCBAJ
"""
import argparse, os, sys
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'ocr'))
from vlm_labels import ask, parse, rotate, ROTATIONS          # noqa: E402
from video_calibrate_test import find_ring, load              # noqa: E402

L10 = 'ABCDEFGHIJ'


def best_vote(votes):
    c = {}
    for v in votes:
        if v and v != '?':
            c[v] = c.get(v, 0) + 1
    return max(c, key=c.get) if c else '?'


def station_offset(samples, n=10):
    tally = {}
    for disp, votes in samples:
        read = best_vote(votes)
        di, ri = L10.find(disp), L10.find(read)
        if di < 0 or ri < 0:
            continue
        tally[(di - ri) % n] = tally.get((di - ri) % n, 0) + 1
    ranked = sorted(tally.items(), key=lambda kv: -kv[1])
    top = ranked[0] if ranked else (0, 0)
    second = ranked[1] if len(ranked) > 1 else (0, 0)
    return top[0], top[1] - second[1]


def snap(letters, nshift, n=10):
    return [L10[(L10.index(c) - nshift) % n] for c in letters]


def read_tag(model, img, x, y, half):
    p = cv2.resize(img[max(0, int(y - half)):int(y + half), max(0, int(x - half)):int(x + half)],
                   (280, 280), interpolation=cv2.INTER_CUBIC)
    return [parse(ask(model, rotate(p, d))) for d in ROTATIONS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--frame', type=int, default=40)
    ap.add_argument('--letters', required=True, help='slot letters from calibration')
    ap.add_argument('--model', default='qwen3-vl:8b'); ap.add_argument('--anchor', type=int, default=5)
    a = ap.parse_args()
    cap = cv2.VideoCapture(a.video); img = load(cap, a.frame); cap.release()
    (hub, R, tags) = find_ring(img); half = int(0.045 * img.shape[1])
    correct = list(a.letters)
    step = max(1, len(tags) // a.anchor)
    idxs = list(range(0, len(tags), step))[:a.anchor]

    # read the sampled tags once; reuse for both conditions
    reads = {i: read_tag(a.model, img, tags[i][0], tags[i][1], half) for i in idxs}
    print(f'sampled tags {idxs}: reads=' + ', '.join(f'{i}:{best_vote(reads[i])}' for i in idxs), flush=True)

    for name, displayed in [('aligned (success)', correct[:]),
                            ('slipped +1 (stability)', snap(correct, -1))]:  # -1 = +1 ahead
        samples = [(displayed[i], reads[i]) for i in idxs]
        n, margin = station_offset(samples, len(tags))
        fixed = snap(displayed, n) if (n != 0 and margin >= 2) else displayed
        ok = fixed == correct
        print(f'  {name:24s} shown={"".join(displayed)} -> detected n={n} margin={margin} '
              f'-> {"".join(fixed)}  [{"OK" if ok else "FAIL"}]', flush=True)


if __name__ == '__main__':
    main()
