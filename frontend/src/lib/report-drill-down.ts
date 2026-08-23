export interface DateRange {
  from: string
  to: string
}

const isoDate = (d: Date) => d.toISOString().slice(0, 10)

/**
 * The dates one report trend bucket covers, inclusive.
 *
 * Bucket labels come straight from the backend's SQL grouping
 * (`_interval_label_expr` in report_service.py): `YYYY-MM-DD` for daily,
 * `YYYY-Www` for weekly (ISO week), `YYYY-MM` for monthly and `YYYY` for
 * yearly. Returns null for a label that doesn't match its interval, so callers
 * skip the drill-down instead of querying a bogus range.
 */
export function bucketDateRange(label: string, interval: string): DateRange | null {
  if (interval === 'daily') {
    return /^\d{4}-\d{2}-\d{2}$/.test(label) ? { from: label, to: label } : null
  }

  if (interval === 'weekly') {
    const match = /^(\d{4})-W(\d{2})$/.exec(label)
    if (!match) return null
    const [year, week] = [Number(match[1]), Number(match[2])]
    // ISO weeks start on Monday, and January 4th always falls in week 1 — so
    // walking back from Jan 4 to its Monday gives week 1's first day.
    const jan4 = new Date(Date.UTC(year, 0, 4))
    const mondayOffset = (jan4.getUTCDay() + 6) % 7
    const monday = new Date(Date.UTC(year, 0, 4 - mondayOffset + (week - 1) * 7))
    const sunday = new Date(monday)
    sunday.setUTCDate(monday.getUTCDate() + 6)
    return { from: isoDate(monday), to: isoDate(sunday) }
  }

  if (interval === 'yearly') {
    return /^\d{4}$/.test(label) ? { from: `${label}-01-01`, to: `${label}-12-31` } : null
  }

  const match = /^(\d{4})-(\d{2})$/.exec(label)
  if (!match) return null
  // Day 0 of the next month is the last day of this one, leap years included.
  const lastDay = new Date(Date.UTC(Number(match[1]), Number(match[2]), 0))
  return { from: `${label}-01`, to: isoDate(lastDay) }
}

/**
 * The whole span a report's trend covers, taken from its buckets rather than
 * recomputing the backend's range math — what the chart shows is what the
 * drill-down lists. Null when no label could be parsed.
 */
export function trendDateRange(labels: string[], interval: string): DateRange | null {
  const ranges = labels
    .map((label) => bucketDateRange(label, interval))
    .filter((range): range is DateRange => range !== null)
  if (ranges.length === 0) return null
  // ISO dates sort lexicographically, so this holds even if labels arrive unordered.
  return {
    from: ranges.reduce((min, r) => (r.from < min ? r.from : min), ranges[0].from),
    to: ranges.reduce((max, r) => (r.to > max ? r.to : max), ranges[0].to),
  }
}
