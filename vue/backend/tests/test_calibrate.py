"""ring_fit() — the part that turns 50%-accurate OCR into a correct assignment.

Votes below are verbatim from the measured 4-rotation sweep of qwen3-vl:8b over
the reference frame (openpose/ocr/vlm_labels.py --mode sweep).
"""
from app.routers.posture import ring_fit

# station label positions on the reference frame, normalized
TAGS = {'A': (0.499, 0.147), 'B': (0.368, 0.150), 'C': (0.259, 0.311),
        'D': (0.233, 0.526), 'E': (0.285, 0.745), 'F': (0.400, 0.859),
        'G': (0.529, 0.834), 'H': (0.626, 0.702), 'I': (0.653, 0.480),
        'J': (0.608, 0.264)}

# 4 rotations each; 50% correct overall, and 'E' is never read correctly at all
READS = {'A': ['?', 'G', 'A', '?'], 'B': ['?', 'B', 'B', 'B'], 'C': ['C', 'C', 'C', 'C'],
         'D': ['D', '?', 'D', '?'], 'E': ['?', 'I', 'H', 'H'], 'F': ['F', 'B', 'H', 'B'],
         'G': ['G', '?', '?', 'G'], 'H': ['H', 'H', 'H', 'H'], 'I': ['H', 'I', 'H', '?'],
         'J': ['H', '?', 'H', 'J']}


def test_recovers_full_assignment_from_noisy_reads():
    got, score, margin = ring_fit(TAGS, READS)
    assert got == {s: s for s in TAGS}
    assert margin > 0, f"ambiguous fit: score={score} margin={margin}"


def test_recovers_a_station_the_model_never_read_correctly():
    assert 'E' not in READS['E']          # guards the premise, not just the result
    assert ring_fit(TAGS, READS)[0]['E'] == 'E'


def test_no_confident_answer_from_useless_reads():
    """All-unknown input must report margin 0 so the caller keeps the manual map."""
    _, _, margin = ring_fit(TAGS, {s: ['?'] * 4 for s in TAGS})
    assert margin == 0


def test_survives_a_single_wrong_letter():
    reads = dict(READS, C=['B', 'B', 'B', 'B'])   # was the only 4/4-correct station
    got, _, margin = ring_fit(TAGS, reads)
    assert got == {s: s for s in TAGS}
    assert margin > 0
