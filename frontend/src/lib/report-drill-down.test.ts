import { describe, expect, it } from 'vitest'

import { bucketDateRange, trendDateRange } from './report-drill-down'

describe('bucketDateRange', () => {
  it('covers a single day for the daily interval', () => {
    expect(bucketDateRange('2025-03-07', 'daily')).toEqual({ from: '2025-03-07', to: '2025-03-07' })
  })

  it('covers Monday through Sunday of an ISO week', () => {
    // 2025-W01 is the week of Dec 30 2024 — ISO weeks can start in the prior year.
    expect(bucketDateRange('2025-W01', 'weekly')).toEqual({ from: '2024-12-30', to: '2025-01-05' })
    expect(bucketDateRange('2025-W10', 'weekly')).toEqual({ from: '2025-03-03', to: '2025-03-09' })
  })

  it('covers a whole month, leap years included', () => {
    expect(bucketDateRange('2025-02', 'monthly')).toEqual({ from: '2025-02-01', to: '2025-02-28' })
    expect(bucketDateRange('2024-02', 'monthly')).toEqual({ from: '2024-02-01', to: '2024-02-29' })
  })

  it('covers a whole year', () => {
    expect(bucketDateRange('2025', 'yearly')).toEqual({ from: '2025-01-01', to: '2025-12-31' })
  })

  it('returns null when the label does not match the interval', () => {
    expect(bucketDateRange('2025-03', 'daily')).toBeNull()
    expect(bucketDateRange('2025-03-07', 'monthly')).toBeNull()
    expect(bucketDateRange('', 'monthly')).toBeNull()
  })
})

describe('trendDateRange', () => {
  it('spans from the first bucket to the last', () => {
    expect(trendDateRange(['2025-01', '2025-02', '2025-03'], 'monthly')).toEqual({
      from: '2025-01-01',
      to: '2025-03-31',
    })
  })

  it('ignores unparseable labels and returns null when none survive', () => {
    expect(trendDateRange(['nope', '2025-05'], 'monthly')).toEqual({
      from: '2025-05-01',
      to: '2025-05-31',
    })
    expect(trendDateRange(['nope'], 'monthly')).toBeNull()
    expect(trendDateRange([], 'monthly')).toBeNull()
  })
})
