// frontend/src/lib/liveRing.js
// ═══════════════════════════════════════════════════════════════════
// Runtime ring rotation. The VLM reads the letters ONCE at calibration; after
// that no model runs. Every ~300 ms the backend re-detects the ring with the
// hub+radius LOCKED (only the angular offset is searched), and these helpers
// rotate the calibrated letters rigidly by the median tag rotation — so the
// overlay turns with the carousel, robust to a partly-occluded ring, and
// never dead-reckons (each measurement is absolute, nothing integrates drift).
// ═══════════════════════════════════════════════════════════════════
import { bearing } from './carousel.js'

/** Signed bearing delta a→b in (−180,180]. */
function signedDelta(a, b) {
  return ((b - a + 540) % 360) - 180
}

/**
 * Rotation between the previous ring and a fresh detection, robustly. Each new
 * tag is matched to the nearest previous tag by bearing; the rotation is the
 * MEDIAN of those signed deltas, so a few tags lost under the operator's hand
 * (or a stray detection) cannot swing it. Returns { deg, inliers }.
 */
export function estimateRotation(prev, ring, aspect = 1, tolDeg = 8) {
  if (!prev?.tags?.length || !ring?.tags?.length) return { deg: 0, inliers: 0 }
  const pb = prev.tags.map(t => bearing(t, prev.hub, aspect))
  const deltas = ring.tags.map((t) => {
    const b = bearing(t, ring.hub, aspect)
    return pb.reduce((best, x) => {
      const s = signedDelta(x, b)
      return Math.abs(s) < Math.abs(best) ? s : best
    }, 180)
  }).sort((a, b) => a - b)
  const deg = deltas[deltas.length >> 1]
  const inliers = deltas.filter(d => Math.abs(d - deg) <= tolDeg).length
  return { deg, inliers }
}

/** Calibration with every tag rotated `deg` about the hub (screen coords,
 *  positive = clockwise). `aspect` = frame H/W: rotate in real-image units,
 *  then map back to normalized so a 16:9 frame isn't skewed. */
export function rotateCal(cal, deg, aspect = 1) {
  if (!cal || !deg) return cal
  const r = deg * Math.PI / 180, cos = Math.cos(r), sin = Math.sin(r)
  const { hub } = cal
  return {
    ...cal,
    tags: cal.tags.map(t => {
      const u = t.x - hub.x, v = (t.y - hub.y) * aspect
      return { ...t, x: hub.x + u * cos - v * sin, y: hub.y + (u * sin + v * cos) / aspect }
    }),
  }
}

/**
 * Advance the calibration to follow the carousel. Rotates every letter rigidly
 * by the median rotation, so the whole ring turns together and a partial
 * occlusion can't tear it apart. Returns the rotated calibration, or null when
 * too few tags agree (`minInliers`) — a genuine loss of lock, hold and wait.
 */
export function carryLetters(prev, ring, aspect = 1, minInliers = 6) {
  if (!prev?.tags?.length || !ring?.tags?.length) return null
  const { deg, inliers } = estimateRotation(prev, ring, aspect)
  if (inliers < minInliers) return null
  return { ...rotateCal(prev, deg, aspect), hub: ring.hub, radius: ring.radius }
}

// ── slip re-anchor ──────────────────────────────────────────────────
// The rotation tracker is blind to the ring's 10-fold symmetry: a turn faster
// than half a wedge between ticks aliases and the letters slip one whole
// station, which then sticks. Nothing geometric can catch it. So when the
// carousel settles, re-read a few tags with the VLM (the only signal that
// breaks the symmetry) and snap the labels back if they are a whole number of
// stations off. Fires once per settle — not a continuous re-calibration.
const RING_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

/** Most-common valid A–Z vote, or '?' if none. */
export function bestVote(votes) {
  const c = {}
  let best = '?', bc = 0
  for (const v of votes || []) {
    if (!v || v === '?') continue
    c[v] = (c[v] || 0) + 1
    if (c[v] > bc) { bc = c[v]; best = v }
  }
  return best
}

/**
 * How many stations the tracked labels are AHEAD of the physical stamps.
 * `samples` = [{displayed, votes}] for a few tags read live. Returns
 * { n, count, margin }: n stations ahead (0 = aligned), margin = lead of the
 * winning offset over the runner-up (a weak/split read gives a small margin,
 * and the caller then declines to snap).
 */
export function stationOffset(samples, stations = 10) {
  const L = RING_LETTERS.slice(0, stations)
  const tally = {}
  for (const s of samples || []) {
    const read = bestVote(s.votes)
    const di = L.indexOf(s.displayed), ri = L.indexOf(read)
    if (di < 0 || ri < 0) continue
    const off = ((di - ri) % stations + stations) % stations
    tally[off] = (tally[off] || 0) + 1
  }
  const ranked = Object.entries(tally).sort((a, b) => b[1] - a[1])
  const top = ranked[0] || ['0', 0], second = ranked[1] || ['0', 0]
  return { n: Number(top[0]), count: top[1], margin: top[1] - second[1] }
}

/** Relabel every tag back by `n` stations, positions untouched (geometry is fine;
 *  only the letter→position mapping slipped). */
export function snapCal(cal, n, stations = 10) {
  if (!cal || !n) return cal
  const L = RING_LETTERS.slice(0, stations)
  return {
    ...cal,
    tags: cal.tags.map(t => {
      const i = L.indexOf(t.letter)
      return i < 0 ? t : { ...t, letter: L[((i - n) % stations + stations) % stations] }
    }),
  }
}
