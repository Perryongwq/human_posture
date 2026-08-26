// frontend/src/lib/liveRing.test.js
import { describe, it, expect } from 'vitest'
import { carryLetters, estimateRotation, rotateCal } from './liveRing.js'

const HUB = { x: 0.5, y: 0.5 }, R = 0.2
const tagAt = deg => ({ x: HUB.x + R * Math.cos(deg * Math.PI / 180), y: HUB.y + R * Math.sin(deg * Math.PI / 180) })
const cal = (offset, letters = 'ABCDEFGHIJ') => ({
  hub: HUB, radius: R,
  tags: [...letters].map((letter, i) => ({ ...tagAt(offset + 36 * i), letter })),
})
const ring = offset => ({ hub: HUB, radius: R, tags: [...Array(10)].map((_, i) => tagAt(offset + 36 * i)) })

describe('rotateCal', () => {
  it('rotates every tag rigidly about the hub', () => {
    expect(rotateCal(cal(0), 36).tags.find(t => t.letter === 'A').x).toBeCloseTo(tagAt(36).x, 6)
  })
  it('is a no-op for 0° or null', () => {
    expect(rotateCal(cal(0), 0).tags[0].x).toBeCloseTo(tagAt(0).x, 9)
    expect(rotateCal(null, 36)).toBeNull()
  })
})

describe('estimateRotation', () => {
  it('recovers a clean rotation as the median delta', () => {
    const { deg, inliers } = estimateRotation(cal(0), ring(8))
    expect(deg).toBeCloseTo(8, 1)
    expect(inliers).toBe(10)
  })
  it('ignores a few occluded/garbage tags (median is robust)', () => {
    const r = ring(10)
    r.tags[0] = tagAt(200); r.tags[3] = tagAt(310)
    const { deg, inliers } = estimateRotation(cal(0), r)
    expect(deg).toBeCloseTo(10, 0)
    expect(inliers).toBeGreaterThanOrEqual(8)
  })
})

describe('carryLetters', () => {
  it('turns the whole ring rigidly with the carousel', () => {
    const next = carryLetters(cal(0), ring(8))
    expect(next.tags.map(t => t.letter).sort().join('')).toBe('ABCDEFGHIJ')
    expect(next.tags.find(t => t.letter === 'A').x).toBeCloseTo(tagAt(8).x, 5)
  })
  it('accumulates a full 360° in small steps with no drift', () => {
    let c = cal(0)
    for (let d = 2; d <= 360; d += 2) c = carryLetters(c, ring(d))
    expect(c.tags.map(t => t.letter).join('')).toBe(cal(0).tags.map(t => t.letter).join(''))
  })
  it('keeps tracking when part of the ring is occluded (does NOT freeze)', () => {
    const r = ring(6); r.tags = r.tags.slice(0, 7)     // 3 tags hidden
    expect(carryLetters(cal(0), r)).not.toBeNull()
    expect(carryLetters(cal(0), r).tags.find(t => t.letter === 'A').x).toBeCloseTo(tagAt(6).x, 4)
  })
  it('holds (null) only when too few tags agree', () => {
    const r = ring(6); r.tags = r.tags.slice(0, 4)     // genuine loss of lock
    expect(carryLetters(cal(0), r)).toBeNull()
  })
})
