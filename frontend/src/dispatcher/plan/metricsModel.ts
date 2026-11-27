import type { PlanMetrics } from '../../shared/api/models';

/** Whole-number percentage saved, or null when there is nothing to compare. */
export function milesSaved(plan: PlanMetrics, baseline: PlanMetrics): number | null {
  if (baseline.travel_miles <= 0) return null;
  const saved = ((baseline.travel_miles - plan.travel_miles) / baseline.travel_miles) * 100;
  return Math.round(saved);
}
