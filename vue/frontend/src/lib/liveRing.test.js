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

import { bestVote, stationOffset, snapCal } from './liveRing.js'

describe('slip re-anchor', () => {
  // 10 tags labelled A..J on positions; simulate the overlay one station AHEAD
  // of the stamps (displayed = stamp + 1), which is the observed failure.
  const L = 'ABCDEFGHIJ'
  const shift = (ch, k) => L[(L.indexOf(ch) + k + 10) % 10]

  it('bestVote takes the majority, ignores ?', () => {
    expect(bestVote(['H', '?', 'H', 'I'])).toBe('H')
    expect(bestVote(['?', '?'])).toBe('?')
  })

  it('detects a +1 station slip from a few noisy reads', () => {
    // displayed is +1 ahead; the true stamp (what the VLM reads) is displayed-1
    const samples = ['B', 'D', 'F', 'H', 'J'].map(d => ({
      displayed: d, votes: [shift(d, -1), '?', shift(d, -1), 'X'],   // one garbage vote
    }))
    const { n, margin } = stationOffset(samples, 10)
    expect(n).toBe(1)
    expect(margin).toBeGreaterThanOrEqual(2)
  })

  it('reports n=0 when aligned (no false snap)', () => {
    const samples = ['A', 'C', 'E'].map(d => ({ displayed: d, votes: [d, d] }))
    expect(stationOffset(samples, 10).n).toBe(0)
  })

  it('snapCal corrects a +1 slip so every label lands on its stamp', () => {
    const cal = { hub: {}, radius: 1, tags: [...L].map((letter, i) => ({ x: i, y: 0, letter })) }
    // slip the labels +1 (what the tracker did), then snap back by n=1
    const slipped = { ...cal, tags: cal.tags.map((t, i) => ({ ...t, letter: L[(i + 1) % 10] })) }
    const fixed = snapCal(slipped, 1, 10)
    expect(fixed.tags.map(t => t.letter).join('')).toBe(L)
  })

  it('snapCal is a no-op for n=0', () => {
    const cal = { tags: [{ letter: 'A' }] }
    expect(snapCal(cal, 0)).toBe(cal)
  })
})
