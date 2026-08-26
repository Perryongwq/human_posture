// frontend/src/lib/carousel.js
// ═══════════════════════════════════════════════════════════════════
// Station lookup for the rotating carousel. Replaces the old traced-polygon
// zones: the backend's /posture/calibrate returns the hub and the ten lettered
// tag positions, so a station is an angular sector, not a hand-drawn shape.
//
// A wrist is assigned to the station whose tag shares its bearing from the hub.
// Measured on the 91-frame reference burst: 11.4 deg median bearing error against
// 36 deg-wide wedges, 55/55 wrists landed inside the correct wedge. See goal.md.
//
// All coordinates normalized [0,1]; x and radius are relative to frame WIDTH,
// y to frame HEIGHT, matching what the backend returns.
// ═══════════════════════════════════════════════════════════════════

/** Signed smallest angle between two bearings, in degrees. */
export function angleDelta(a, b) {
  return Math.abs(((a - b + 180) % 360 + 360) % 360 - 180)
}

/** Bearing of a point from the hub, in degrees. */
export function bearing(pt, hub, aspect = 1) {
  return Math.atan2((pt.y - hub.y) * aspect, pt.x - hub.x) * 180 / Math.PI
}

/**
 * Which station a point belongs to.
 *
 * `aspect` converts normalized y back to the same units as x (frame height /
 * width) so bearings are measured on the real image, not a stretched one —
 * getting this wrong skews every angle on a 16:9 frame.
 *
 * Returns null when there is no calibration, or when the point is outside
 * `reach` — a wrist nowhere near the fixture must not snap to the nearest
 * letter just because it happens to share a bearing.
 *
 * @returns {{index, letter, offDeg, reach}|null}
 */
export function stationOf(pt, cal, { aspect = 1, minReach = 0.45, maxReach = 1.35 } = {}) {
  if (!pt || !cal?.tags?.length || !cal.hub || !cal.radius) return null
  const reach = Math.hypot(pt.x - cal.hub.x, (pt.y - cal.hub.y) * aspect) / cal.radius
  if (!(reach > minReach && reach < maxReach)) return null
  const b = bearing(pt, cal.hub, aspect)
  let best = null
  for (let i = 0; i < cal.tags.length; i++) {
    const d = angleDelta(bearing(cal.tags[i], cal.hub, aspect), b)
    if (!best || d < best.offDeg) best = { index: i, letter: cal.tags[i].letter, offDeg: d, reach }
  }
  return best
}
