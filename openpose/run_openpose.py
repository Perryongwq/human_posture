"""OpenPose (CMU) on the carousel photos: arm/hand keypoints + white-glove check.

Two detection layers, reported side by side, because they fail differently here:

  person  - stock OpenPose: heatmap peaks grouped into people via PAFs. Accurate,
            but its grouping stage discards any skeleton with <4 keypoints, so an
            operator whose torso is out of frame (just a forearm reaching in from
            the edge -- the common case on this top-down rig) is never reported.
  peak    - the same network's part heatmaps read directly, no grouping. Gives
            "there is a wrist at (x,y)" without needing a body attached to it.

Weights are the original CMU OpenPose body/hand nets (PyTorch port, via
lllyasviel/Annotators) -- OpenPose's own posefs1.perception.cs.cmu.edu host is dead.
"""
import argparse, json, os, glob
import cv2, numpy as np, torch
from controlnet_aux.open_pose import OpenposeDetector, util

COCO = ['nose', 'neck', 'Rsho', 'Relb', 'Rwri', 'Lsho', 'Lelb', 'Lwri', 'Rhip',
        'Rkne', 'Rank', 'Lhip', 'Lkne', 'Lank', 'Reye', 'Leye', 'Rear', 'Lear']
ARM = {'Rsho': 2, 'Relb': 3, 'Rwri': 4, 'Lsho': 5, 'Lelb': 6, 'Lwri': 7}
WRISTS = ('Rwri', 'Lwri')


# --------------------------------------------------------------------------- peaks
def part_heatmap(model, img_bgr, scale=1.0, boxsize=368, stride=8):
    """Forward pass -> 19-channel part heatmap at input resolution.

    `scale` multiplies OpenPose's boxsize/height normalisation; upstream hardcodes
    0.5, which on a 4K frame leaves the net looking at ~180px of image. Knob, not
    constant -- effective net input height is scale * boxsize.
    """
    s = scale * boxsize / img_bgr.shape[0]
    test = util.smart_resize_k(img_bgr, fx=s, fy=s)
    padded, pad = util.padRightDownCorner(test, stride, 128)
    x = np.transpose(np.float32(padded[:, :, :, None]), (3, 2, 0, 1)) / 256 - 0.5
    dev = next(iter(model.parameters())).device
    with torch.no_grad():
        _, hm = model(torch.from_numpy(np.ascontiguousarray(x)).float().to(dev))
    hm = np.transpose(np.squeeze(hm.cpu().numpy()), (1, 2, 0))
    hm = util.smart_resize_k(hm, fx=stride, fy=stride)
    hm = hm[:padded.shape[0] - pad[2], :padded.shape[1] - pad[3], :]
    return util.smart_resize(hm, (img_bgr.shape[0], img_bgr.shape[1]))


def peaks(hm, ch, thre, top=3):
    """Local maxima of one part channel, strongest first. Same neighbour NMS
    OpenPose uses, minus the person grouping."""
    m = cv2.GaussianBlur(hm[:, :, ch].astype(np.float32), (0, 0), 3)
    mx = cv2.dilate(m, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero((m >= mx) & (m > thre))
    out = sorted(((int(x), int(y), float(m[y, x])) for x, y in zip(xs, ys)),
                 key=lambda p: -p[2])
    return out[:top]


# ----------------------------------------------------------------------- gloves
def cover_at(img_bgr, xy, r, s_max, v_min, skin_h=(0, 30)):
    """White glove vs bare hand at a keypoint, from median HSV of a patch.

    A white knit glove is desaturated and bright; bare skin holds saturation in the
    red-orange hues; the bench floor is saturated green. Thresholds are knobs --
    lighting on this bench will move them.
    """
    if xy is None:
        return None
    h, w = img_bgr.shape[:2]
    x, y = int(xy[0]), int(xy[1])
    x0, x1, y0, y1 = max(0, x - r), min(w, x + r), max(0, y - r), min(h, y + r)
    if x1 <= x0 or y1 <= y0:
        return None
    hsv = cv2.cvtColor(img_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    H, S, V = (float(np.median(hsv[:, i])) for i in range(3))
    if S <= s_max and V >= v_min:
        label = 'glove'
    elif skin_h[0] <= H <= skin_h[1] and S > s_max:
        label = 'bare'
    else:
        label = 'other'          # green floor, dark sleeve, plate shadow
    return {'label': label, 'h': round(H, 1), 's': round(S, 1), 'v': round(V, 1)}


# -------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', default='images')
    ap.add_argument('--out', default='openpose/out')
    ap.add_argument('--width', type=int, default=1280, help='resize longest side before inference')
    ap.add_argument('--scale', type=float, default=1.0, help='net input scale knob (see part_heatmap)')
    ap.add_argument('--peak-thre', type=float, default=0.15, help='part heatmap peak threshold')
    ap.add_argument('--glove-s-max', type=float, default=60, help='max saturation to call a patch glove')
    ap.add_argument('--glove-v-min', type=float, default=120, help='min value to call a patch glove')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--overlays', type=int, default=0, help='write N annotated frames (0 = none)')
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.images, '*.jpg')))[:a.limit or None]
    os.makedirs(os.path.join(a.out, 'overlays'), exist_ok=True)

    det = OpenposeDetector.from_pretrained('lllyasviel/Annotators')
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    for e in (det.body_estimation, det.hand_estimation):
        e.model.to(dev)
        e.cuda = (dev == 'cuda')
    print('%d images | device=%s | width=%d scale=%.2f peak_thre=%.2f'
          % (len(files), dev, a.width, a.scale, a.peak_thre), flush=True)

    rows = []
    for n, f in enumerate(files):
        img = cv2.imread(f)
        sc = a.width / max(img.shape[:2])
        if sc < 1:
            img = cv2.resize(img, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        r = max(8, w // 60)

        poses = det.detect_poses(img, include_hand=True)
        people = []
        for p in poses:
            kp = p.body.keypoints
            j = {nm: (None if i >= len(kp) or kp[i] is None
                      else [round(kp[i].x * w, 1), round(kp[i].y * h, 1)])
                 for nm, i in ARM.items()}
            hands = {}
            for side, hk in (('left', p.left_hand), ('right', p.right_hand)):
                pts = [] if hk is None else [(k.x * w, k.y * h) for k in hk if k is not None]
                hands[side] = {'n_pts': len(pts),
                               'centroid': [round(float(v), 1) for v in np.mean(pts, 0)] if pts else None}
            people.append({'score': round(float(p.body.total_score), 2),
                           'parts': int(p.body.total_parts), 'arm': j, 'hands': hands,
                           'cover': {nm: cover_at(img, j[nm], r, a.glove_s_max, a.glove_v_min)
                                     for nm in WRISTS}})

        hm = part_heatmap(det.body_estimation.model, img, scale=a.scale)
        pk = {}
        for nm, ch in ARM.items():
            pk[nm] = [{'xy': [p[0], p[1]], 'score': round(p[2], 3),
                       'cover': cover_at(img, (p[0], p[1]), r, a.glove_s_max, a.glove_v_min)}
                      for p in peaks(hm, ch, a.peak_thre)]

        rows.append({'file': os.path.basename(f), 'w': w, 'h': h, 'people': people, 'peaks': pk})

        if n < a.overlays:
            c = img.copy()
            for p in poses:
                c = util.draw_bodypose(c, p.body.keypoints)
                c = util.draw_handpose(c, p.left_hand)
                c = util.draw_handpose(c, p.right_hand)
            for nm in ARM:
                for d in pk[nm]:
                    x, y = d['xy']
                    lab = d['cover']['label'] if d['cover'] else '?'
                    col = {'glove': (0, 255, 255), 'bare': (255, 0, 255)}.get(lab, (160, 160, 160))
                    cv2.circle(c, (x, y), 9, col, 2)
                    cv2.putText(c, '%s %.2f %s' % (nm, d['score'], lab),
                                (x + 11, y - 6), 0, 0.45, col, 1)
            cv2.imwrite(os.path.join(a.out, 'overlays', os.path.basename(f)[:-4] + '.png'), c)
        print('[%d/%d] %s: person=%d wri_peaks=%d'
              % (n + 1, len(files), os.path.basename(f), len(poses),
                 len(pk['Rwri']) + len(pk['Lwri'])), flush=True)

    with open(os.path.join(a.out, 'results.json'), 'w') as fh:
        json.dump(rows, fh, indent=1)

    N = len(rows)
    hit = lambda pred: sum(bool(pred(r)) for r in rows)
    print('\n=== detection rate over %d images ===' % N)
    print('  %-24s %3d/%d' % ('person (grouped)', hit(lambda r: r['people']), N))
    for nm in ARM:
        g = hit(lambda r, nm=nm: any(p['arm'][nm] for p in r['people']))
        q = hit(lambda r, nm=nm: r['peaks'][nm])
        print('  %-8s person %3d/%d (%3.0f%%)   peak %3d/%d (%3.0f%%)'
              % (nm, g, N, 100 * g / N, q, N, 100 * q / N))
    for side in ('left', 'right'):
        c = hit(lambda r, s=side: any(p['hands'][s]['n_pts'] for p in r['people']))
        print('  %-24s %3d/%d (%3.0f%%)' % (side + ' hand-21', c, N, 100 * c / N))

    cov = [d['cover']['label'] for r in rows for nm in WRISTS for d in r['peaks'][nm] if d['cover']]
    print('\n  wrist-peak patch classes: '
          + ', '.join('%s=%d' % (k, cov.count(k)) for k in ('glove', 'bare', 'other'))
          + '  (n=%d)' % len(cov))
    print('\nwrote %s/results.json' % a.out
          + (' and %d overlays' % min(a.overlays, N) if a.overlays else ''))


if __name__ == '__main__':
    main()
