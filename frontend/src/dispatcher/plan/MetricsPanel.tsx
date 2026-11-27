import { useEffect, useState } from 'react';
import { fetchScheduleMetrics } from '../../shared/api/client';
import type { DayMetrics, PlanMetrics } from '../../shared/api/models';
import { ui } from '../../shared/ui';
import { milesSaved } from './metricsModel';

type Row = { label: string; value: (m: PlanMetrics) => string };

const ROWS: Row[] = [
  { label: 'Jobs placed', value: (m) => String(m.jobs - m.unplaced) },
  { label: 'Could not be placed', value: (m) => String(m.unplaced) },
  { label: 'SLA breaches', value: (m) => String(m.sla_breaches) },
  { label: 'Minutes late', value: (m) => String(m.late_minutes) },
  { label: 'Miles driven', value: (m) => m.travel_miles.toFixed(1) },
  {
    label: 'Workload spread (max − min jobs)',
    value: (m) => String(m.workload_spread),
  },
];

/** Before/after: this day as planned, against dealing the same jobs out round-robin. */
export default function MetricsPanel({ date, refreshKey }: { date: string; refreshKey: unknown }) {
  const [metrics, setMetrics] = useState<DayMetrics | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    void (async () => {
      try {
        const next = await fetchScheduleMetrics(date);
        if (current) {
          setMetrics(next);
          setFailed(false);
        }
      } catch {
        if (current) setFailed(true);
      }
    })();
    return () => {
      current = false;
    };
  }, [date, refreshKey]);

  if (failed) return <p className={`${ui.muted} mb-4`}>Could not load the comparison.</p>;
  if (!metrics || metrics.jobs === 0) return null;
  const saved = milesSaved(metrics.plan, metrics.baseline);

  return (
    <section aria-labelledby="metrics-title" className="mb-6">
      <h2 id="metrics-title" className="mb-1 text-xl font-bold">
        Planner vs round-robin
      </h2>
      <p className={`${ui.muted} mb-3`}>
        The same {metrics.jobs} {metrics.jobs === 1 ? 'job' : 'jobs'}, timed from the start of the
        day. Round-robin deals jobs out in turn to technicians who have the skill, ignoring
        distance, load and deadlines.
        {metrics.in_queue > 0 && ` ${metrics.in_queue} still in the queue are not counted.`}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th scope="col" className="py-1 pr-4"></th>
              <th scope="col" className="py-1 pr-4">
                Planner
              </th>
              <th scope="col" className="py-1">
                Round-robin
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label} className="border-t border-line">
                <th scope="row" className="py-1 pr-4 font-normal">
                  {row.label}
                </th>
                <td className="py-1 pr-4 font-semibold">{row.value(metrics.plan)}</td>
                <td className="py-1">{row.value(metrics.baseline)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {saved !== null && saved > 0 && (
        <p className="mt-2 text-sm font-semibold">The planner drives {saved}% fewer miles.</p>
      )}
    </section>
  );
}
