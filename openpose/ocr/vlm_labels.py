"""Station-letter recognition via a local VLM (Ollama), replacing Tesseract.

Tesseract scored 0% on these labels (goal.md 2026-07-15). Three reasons, all
visible in openpose/ocr/montage.png: the letters are stamped bolt-head markings
~15-20px wide in the raw frame, they are dirty and low-contrast, and -- the one
nobody accounted for -- each sits at a *different rotation*, because the stations
are arranged radially. Tesseract assumes upright text.

Recognition runs ONCE at calibration, not per frame: the carousel is static while
an operator works it (goal.md 2026-08-20), so a station's screen position and its
letter are both fixed for the session. Latency is irrelevant here; accuracy is not.

`--sweep` measures accuracy at each of 4 rotations to establish which orientation
the stamped letters actually read at; `--vote` is the production strategy that
falls out of it -- ask at every rotation, take the majority answer.
"""
import argparse, base64, json, time
import urllib.request
import cv2, numpy as np

OLLAMA = 'http://localhost:11434/api/generate'
LETTERS = 'ABCDEFGHIJ'
ROTATIONS = [0, 90, 180, 270]

PROMPT = (
    'This image shows a single capital letter stamped on a round metal bolt head. '
    'The letter may be dirty, worn, or upside down. '
    f'It is one of these ten: {", ".join(LETTERS)}. '
    'Answer with that one letter only.'
)

# label-tag centres in source px, calibrated once against the reference frame
TAGS = {'A': (1914, 317), 'B': (1415, 323), 'C': (996, 672), 'D': (895, 1137),
        'E': (1096, 1609), 'F': (1536, 1855), 'G': (2031, 1801), 'H': (2404, 1517),
        'I': (2506, 1037), 'J': (2335, 570)}


def ask(model, img, timeout=300):
    """One VLM call. No num_predict cap -- qwen3-vl emits a thinking block first
    and a low cap truncates it before the answer ever reaches `response`."""
    body = json.dumps({
        'model': model, 'prompt': PROMPT,
        'images': [base64.b64encode(cv2.imencode('.png', img)[1]).decode()],
        'stream': False, 'think': False,
        'options': {'temperature': 0},
    }).encode()
    req = urllib.request.Request(OLLAMA, body, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r).get('response', '')


def parse(text):
    """First A-J character in the reply, or '?'."""
    for ch in (text or '').upper():
        if ch in LETTERS:
            return ch
    return '?'


def crop(img, cx, cy, r, out=280):
    """Square crop about (cx, cy), upscaled -- a VLM fed the whole 4K frame sees
    the letter at ~15px and fails the same way Tesseract did."""
    h, w = img.shape[:2]
    patch = img[max(0, cy - r):min(h, cy + r), max(0, cx - r):min(w, cx + r)]
    return cv2.resize(patch, (out, out), interpolation=cv2.INTER_CUBIC)


def rotate(patch, deg):
    if deg % 360 == 0:
        return patch
    h, w = patch.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(patch, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def vote(model, patch):
    """Production strategy: read the crop at all 4 rotations, take the majority.
    Orientation is unknown per station and a wrong guess costs a whole label, so
    4 cheap calls beat one clever one. Returns (letter, agreement 0-4)."""
    picks = [parse(ask(model, rotate(patch, d))) for d in ROTATIONS]
    good = [p for p in picks if p != '?']
    if not good:
        return '?', 0
    best = max(set(good), key=good.count)
    return best, good.count(best)


def ring_fit(tags, reads):
    """Assign A-J to stations using the fixture's geometry, not just the OCR.

    The ten stations sit in strict alphabetical order around the hub at 36 deg
    steps (measured: mean 36.1, spread 34-39). That leaves only 20 possible
    assignments -- 10 rotational offsets x 2 directions -- so the letters do not
    have to be read correctly, only *mostly* correctly. Scoring each hypothesis
    against the raw votes recovers stations the VLM never read right at all.

    tags:  {station_key: (x, y)}          -- label positions in image px
    reads: {station_key: [letter, ...]}   -- every VLM vote for that station
    returns (assignment, score, margin). A small margin means the reads were too
    noisy to trust -- fall back to manual tap rather than guessing.
    """
    keys = list(tags)
    cx = sum(tags[k][0] for k in keys) / len(keys)
    cy = sum(tags[k][1] for k in keys) / len(keys)
    ring = sorted(keys, key=lambda k: np.degrees(np.arctan2(tags[k][1] - cy,
                                                            tags[k][0] - cx)) % 360)
    n = len(ring)
    scored = []
    for direction in (1, -1):
        for off in range(n):
            guess = {ring[i]: LETTERS[(off + direction * i) % n] for i in range(n)}
            scored.append((sum(reads[s].count(guess[s]) for s in ring), guess))
    scored.sort(key=lambda t: -t[0])
    return scored[0][1], scored[0][0], scored[0][0] - scored[1][0]


def _self_check():
    """Verbatim VLM votes from the 4-rotation sweep on the reference frame:
    50% raw OCR accuracy, and station E read wrong at every rotation."""
    reads = {'A': ['?', 'G', 'A', '?'], 'B': ['?', 'B', 'B', 'B'], 'C': ['C', 'C', 'C', 'C'],
             'D': ['D', '?', 'D', '?'], 'E': ['?', 'I', 'H', 'H'], 'F': ['F', 'B', 'H', 'B'],
             'G': ['G', '?', '?', 'G'], 'H': ['H', 'H', 'H', 'H'], 'I': ['H', 'I', 'H', '?'],
             'J': ['H', '?', 'H', 'J']}
    got, score, margin = ring_fit(TAGS, reads)
    assert all(got[s] == s for s in LETTERS), got
    assert margin > 0, margin
    # a station nobody read correctly is still recovered by the ring constraint
    assert 'E' not in reads['E'] and got['E'] == 'E'
    # degenerate input must not silently produce a confident answer
    _, _, m0 = ring_fit(TAGS, {s: ['?'] * 4 for s in LETTERS})
    assert m0 == 0, m0
    print(f'ok — 10/10 from 50%-accurate reads, score={score} margin={margin}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', default='images/WIN_20260820_13_30_47_Pro.jpg')
    ap.add_argument('--model', default='qwen3-vl:8b')
    ap.add_argument('--radius', type=int, default=70, help='half-size of the label crop, source px')
    ap.add_argument('--mode', choices=['sweep', 'vote', 'ring', 'selfcheck'], default='ring')
    a = ap.parse_args()

    if a.mode == 'selfcheck':
        return _self_check()

    img = cv2.imread(a.image)
    print(f'model={a.model}  image={a.image}  mode={a.mode}\n')
    t0 = time.time()

    if a.mode == 'sweep':
        hits = {d: 0 for d in ROTATIONS}
        print(f'{"gt":>3} ' + ' '.join(f'{d:>5}' for d in ROTATIONS))
        for gt in LETTERS:
            patch = crop(img, *TAGS[gt], a.radius)
            row = []
            for d in ROTATIONS:
                p = parse(ask(a.model, rotate(patch, d)))
                hits[d] += p == gt
                row.append(f'{p:>5}' if p != gt else f'{p + "*":>5}')
            print(f'{gt:>3} ' + ' '.join(row), flush=True)
        n = len(LETTERS)
        print('\n  accuracy by rotation (* = correct):')
        for d in ROTATIONS:
            print(f'    {d:>3} deg  {hits[d]}/{n} ({hits[d]/n:.0%})')
    elif a.mode == 'ring':
        reads = {}
        for gt in LETTERS:
            patch = crop(img, *TAGS[gt], a.radius)
            reads[gt] = [parse(ask(a.model, rotate(patch, d))) for d in ROTATIONS]
            print(f'{gt:>3} read {reads[gt]}', flush=True)
        got, score, margin = ring_fit(TAGS, reads)
        ok = sum(got[s] == s for s in LETTERS)
        raw = sum(reads[s].count(s) > 0 for s in LETTERS)
        print(f'\n  letters read correctly at >=1 rotation : {raw}/10')
        print(f'  after ring fit                        : {ok}/10  (score {score}, margin {margin})')
        print('  assignment:', {s: got[s] for s in LETTERS})
    else:
        ok = 0
        print(f'{"gt":>3} {"pred":>5} {"votes":>6}')
        for gt in LETTERS:
            p, v = vote(a.model, crop(img, *TAGS[gt], a.radius))
            ok += p == gt
            print(f'{gt:>3} {p:>5} {v:>4}/4' + ('' if p == gt else '   <-- wrong'), flush=True)
        n = len(LETTERS)
        print(f'\n  4-rotation majority vote: {ok}/{n} ({ok/n:.0%})')

    print(f'  {time.time()-t0:.0f}s total')


if __name__ == '__main__':
    main()
