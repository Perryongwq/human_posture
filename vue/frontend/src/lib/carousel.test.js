// frontend/src/lib/carousel.test.js
import { describe, it, expect } from 'vitest'
import { stationOf, bearing, angleDelta } from './carousel.js'

// square frame (aspect 1) so the expected geometry is obvious by hand:
// hub at centre, ten tags at 36 deg steps on a 0.4 radius, lettered A..J
const HUB = { x: 0.5, y: 0.5 }
const R = 0.4
const CAL = {
  hub: HUB,
  radius: R,
  tags: [...'ABCDEFGHIJ'].map((letter, i) => ({
    x: HUB.x + R * Math.cos(i * 36 * Math.PI / 180),
    y: HUB.y + R * Math.sin(i * 36 * Math.PI / 180),
    letter,
  })),
}

const at = (deg, reach) => ({
  x: HUB.x + R * reach * Math.cos(deg * Math.PI / 180),
  y: HUB.y + R * reach * Math.sin(deg * Math.PI / 180),
})

describe('angleDelta', () => {
  it('is the smallest angle, and wraps across 0/360', () => {
    expect(angleDelta(10, 350)).toBeCloseTo(20, 6)
    expect(angleDelta(350, 10)).toBeCloseTo(20, 6)
    expect(angleDelta(-170, 170)).toBeCloseTo(20, 6)
    expect(angleDelta(90, 90)).toBeCloseTo(0, 6)
  })
})

describe('stationOf', () => {
  it('picks the tag sharing the point bearing', () => {
    expect(stationOf(at(0, 1.0), CAL).letter).toBe('A')
    expect(stationOf(at(72, 1.0), CAL).letter).toBe('C')
    expect(stationOf(at(180, 1.0), CAL).letter).toBe('F')
  })

  it('still resolves inside the wedge, not only dead on the tag', () => {
    // a wedge is 36 deg, so +/-17 deg off the tag must stay on that tag
    const s = stationOf(at(72 + 17, 1.0), CAL)
    expect(s.letter).toBe('C')
    expect(s.offDeg).toBeCloseTo(17, 4)
  })

  it('rejects a point too far out or too far in, rather than snapping', () => {
    expect(stationOf(at(0, 2.0), CAL)).toBe(null)   // out past the fixture
    expect(stationOf(at(0, 0.1), CAL)).toBe(null)   // on the hub
  })

  it('null without calibration', () => {
    expect(stationOf(at(0, 1), null)).toBe(null)
    expect(stationOf(at(0, 1), { hub: HUB, radius: R, tags: [] })).toBe(null)
    expect(stationOf(null, CAL)).toBe(null)
  })

  it('aspect correction changes the bearing on a non-square frame', () => {
    // a 16:9 frame squashes y; without correcting, a 45 deg point reads ~68 deg
    const p = { x: 0.6, y: 0.6 }
    expect(bearing(p, HUB, 1)).toBeCloseTo(45, 4)
    expect(bearing(p, HUB, 9 / 16)).toBeCloseTo(29.36, 1)
  })
})
