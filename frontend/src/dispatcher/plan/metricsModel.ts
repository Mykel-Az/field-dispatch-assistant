import type { PlanMetrics } from '../../shared/api/models';

export type Winner = 'planner' | 'baseline' | 'same';

export interface Measure {
  key: string;
  label: string;
  /** What lower means, in a few words, for the caption under the label. */
  hint: string;
  value: (m: PlanMetrics) => number;
  format: (n: number) => string;
}

/** Every measure here is "lower is better". */
export const MEASURES: Measure[] = [
  {
    key: 'breaches',
    label: 'Late arrivals',
    hint: 'jobs that miss their window',
    value: (m) => m.sla_breaches,
    format: (n) => String(n),
  },
  {
    key: 'late',
    label: 'Minutes late',
    hint: 'added up over all jobs',
    value: (m) => m.late_minutes,
    format: (n) => `${Math.round(n)} min`,
  },
  {
    key: 'miles',
    label: 'Driving',
    hint: 'miles, in straight lines',
    value: (m) => m.travel_miles,
    format: (n) => `${n.toFixed(1)} mi`,
  },
  {
    key: 'spread',
    label: 'Uneven workload',
    hint: 'most jobs minus fewest, per technician',
    value: (m) => m.workload_spread,
    format: (n) => String(n),
  },
];

/** Lower wins. Miles are compared to a tenth, so rounding noise is not a win. */
export function winner(measure: Measure, plan: PlanMetrics, baseline: PlanMetrics): Winner {
  const a = Math.round(measure.value(plan) * 10);
  const b = Math.round(measure.value(baseline) * 10);
  return a < b ? 'planner' : a > b ? 'baseline' : 'same';
}

/** Bar length as a share of the longer of the two, so the pair is read against each other. */
export function barWidths(plan: number, baseline: number): [number, number] {
  const longest = Math.max(plan, baseline);
  if (longest <= 0) return [0, 0];
  const width = (n: number) => (n <= 0 ? 0 : Math.max(3, (n / longest) * 100));
  return [width(plan), width(baseline)];
}
