"""Self-check for the two pure functions in run_openpose.py. `python openpose/test_run_openpose.py`"""
import sys, os
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_openpose import peaks, cover_at


def test_peaks():
    # blobs, not single pixels -- peaks() blurs with sigma=3 like OpenPose does
    hm = np.zeros((100, 100, 19), np.float32)
    ch = np.zeros((100, 100), np.float32)
    cv2.circle(ch, (40, 30), 5, 1.0, -1)             # strong
    cv2.circle(ch, (80, 70), 5, 0.5, -1)             # weaker
    cv2.circle(ch, (10, 10), 5, 0.02, -1)            # below threshold
    hm[:, :, 4] = ch
    got = peaks(hm, 4, thre=0.05, top=5)
    assert len(got) == 2, got                       # sub-threshold peak dropped
    assert (got[0][0], got[0][1]) == (40, 30), got  # strongest first
    assert (got[1][0], got[1][1]) == (80, 70), got
    assert got[0][2] > got[1][2]
    assert peaks(hm, 4, thre=0.05, top=1) == got[:1]
    assert peaks(hm, 5, thre=0.05) == []            # empty channel


def _patch(bgr):
    img = np.zeros((60, 60, 3), np.uint8)
    img[:] = bgr
    return img


def test_cover_at():
    args = dict(r=20, s_max=60, v_min=120)
    assert cover_at(_patch((235, 235, 235)), (30, 30), **args)['label'] == 'glove'   # white knit
    assert cover_at(_patch((120, 150, 200)), (30, 30), **args)['label'] == 'bare'    # skin
    assert cover_at(_patch((60, 160, 60)), (30, 30), **args)['label'] == 'other'     # bench floor
    assert cover_at(_patch((30, 30, 30)), (30, 30), **args)['label'] == 'other'      # dark sleeve
    assert cover_at(_patch((235, 235, 235)), None, **args) is None
    assert cover_at(_patch((235, 235, 235)), (-99, -99), **args) is None             # off-frame


if __name__ == '__main__':
    test_peaks()
    test_cover_at()
    print('ok')
