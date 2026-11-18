import type { PlanMapData } from './planMapModel';

/** Under the map: who is which colour, and what the lines are (and are not). */
export default function PlanMapKey({ data, hasOffice }: { data: PlanMapData; hasOffice: boolean }) {
  return (
    <div className="mt-2 grid gap-1 text-sm text-ink-muted">
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {data.routes.map((r) => (
          <li key={r.technicianId} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block size-3 rounded-full" style={{ background: r.color }} />
            {r.name}
          </li>
        ))}
        {data.misses.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block size-3 rounded-full border-2 border-dashed border-warn-ink" />
            Not assigned
          </li>
        )}
        {hasOffice && (
          <li className="flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block size-3 rounded bg-ink" />
            Office
          </li>
        )}
      </ul>
      <p>
        Numbers are the visit order. Lines join the stops in that order
        {hasOffice ? ', starting at the office' : ''}; they are straight lines, not road routes.
      </p>
      {data.unplaced > 0 && (
        <p role="note">
          {data.unplaced} planned {data.unplaced === 1 ? 'stop is' : 'stops are'} not on the map because{' '}
          {data.unplaced === 1 ? 'its' : 'their'} location is not known.
        </p>
      )}
    </div>
  );
}
