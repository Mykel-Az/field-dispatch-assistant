import { useEffect, useState } from 'react';
import { fetchScheduleMetrics } from '../../shared/api/client';
import type { DayMetrics } from '../../shared/api/models';
import { ui } from '../../shared/ui';
import { barWidths, MEASURES, winner, type Winner } from './metricsModel';

const VERDICT: Record<Winner, { glyph: string; text: string }> = {
  planner: { glyph: '✓', text: 'Planner is better' },
  baseline: { glyph: '✗', text: 'Round-robin is better' },
  same: { glyph: '=', text: 'Same' },
};

function Bar({
  name,
  shown,
  width,
  strong,
}: {
  name: string;
  shown: string;
  width: number;
  strong: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-24 shrink-0">{name}</span>
      <div className="h-3 flex-1 rounded bg-canvas" aria-hidden="true">
        <div
          className={`h-3 rounded ${strong ? 'bg-brand' : 'bg-line-strong'}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className={`w-16 shrink-0 text-right tabular-nums ${strong ? 'font-bold' : ''}`}>
        {shown}
      </span>
    </div>
  );
}

/** The day as planned against dealing the same jobs out round-robin: shorter bars are better. */
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

  const results = MEASURES.map((m) => ({ m, w: winner(m, metrics.plan, metrics.baseline) }));
  const better = results.filter((r) => r.w === 'planner').length;
  const worse = results.filter((r) => r.w === 'baseline').length;
  const unplaced = metrics.plan.unplaced > 0 || metrics.baseline.unplaced > 0;

  return (
    <section aria-labelledby="metrics-title" className="mb-6">
      <h2 id="metrics-title" className="mb-1 text-xl font-bold">
        Planner vs round-robin
      </h2>
      <p className="mb-1 font-semibold">
        The planner is better on {better} of {MEASURES.length} measures
        {worse > 0 ? ` and worse on ${worse}` : ''}.
      </p>
      <p className={`${ui.muted} mb-3`}>
        The same {metrics.jobs} {metrics.jobs === 1 ? 'job' : 'jobs'}, timed from the start of the
        day. Round-robin deals jobs out in turn to technicians who have the skill, ignoring
        distance, load and deadlines. Shorter bars are better.
        {metrics.in_queue > 0 && ` ${metrics.in_queue} still in the queue are not counted.`}
      </p>
      <ul className="grid gap-3 md:grid-cols-2">
        {results.map(({ m, w }) => {
          const [planWidth, baseWidth] = barWidths(
            m.value(metrics.plan),
            m.value(metrics.baseline),
          );
          const verdict = VERDICT[w];
          return (
            <li key={m.key} className={ui.card}>
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3">
                <h3 className="font-bold">{m.label}</h3>
                <span className="text-sm font-semibold">
                  <span aria-hidden="true">{verdict.glyph} </span>
                  {verdict.text}
                </span>
              </div>
              <div className="space-y-1.5">
                <Bar
                  name="Planner"
                  shown={m.format(m.value(metrics.plan))}
                  width={planWidth}
                  strong
                />
                <Bar
                  name="Round-robin"
                  shown={m.format(m.value(metrics.baseline))}
                  width={baseWidth}
                  strong={false}
                />
              </div>
              <p className={`${ui.muted} mt-2 text-sm`}>{m.hint}</p>
            </li>
          );
        })}
      </ul>
      {unplaced && (
        <p className={`${ui.notice} mt-3`}>
          Jobs that could not be placed: planner {metrics.plan.unplaced}, round-robin{' '}
          {metrics.baseline.unplaced}.
        </p>
      )}
    </section>
  );
}
