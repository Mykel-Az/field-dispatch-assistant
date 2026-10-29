// One definition of the seven job statuses, used by the badges, the list
// filters and (S1-5) the map pins. Class names are written out in full so
// Tailwind can see them.

export const JOB_STATUSES = [
  'unassigned',
  'assigned',
  'ongoing',
  'completed',
  'incomplete',
  'failed',
  'canceled',
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];

export interface StatusMeta {
  label: string;
  /** Tailwind classes for the pill: tinted background and coloured text. */
  badge: string;
  /** Solid status colour for accent bars. */
  bar: string;
  /** CSS variable holding the pin fill, e.g. for style={{ fill: meta.pin }}. */
  pin: string;
  /** SVG path drawn inside the pin and the badge dot, so shape differs too. */
  glyph: string;
}

export const STATUS_META: Record<JobStatus, StatusMeta> = {
  unassigned: {
    label: 'Unassigned',
    badge: 'bg-st-unassigned-soft text-st-unassigned',
    bar: 'bg-st-unassigned',
    pin: 'var(--st-unassigned-pin)',
    glyph: 'M7 9h4', // dash: nobody yet
  },
  assigned: {
    label: 'Assigned',
    badge: 'bg-st-assigned-soft text-st-assigned',
    bar: 'bg-st-assigned',
    pin: 'var(--st-assigned-pin)',
    glyph: 'M9 9h.01', // dot: someone is on it
  },
  ongoing: {
    label: 'Ongoing',
    badge: 'bg-st-ongoing-soft text-st-ongoing',
    bar: 'bg-st-ongoing',
    pin: 'var(--st-ongoing-pin)',
    glyph: 'M8 6.8l3 2.2-3 2.2z', // play
  },
  completed: {
    label: 'Completed',
    badge: 'bg-st-completed-soft text-st-completed',
    bar: 'bg-st-completed',
    pin: 'var(--st-completed-pin)',
    glyph: 'M7 9.2l1.5 1.5L11 7.8', // check
  },
  incomplete: {
    label: 'Incomplete',
    badge: 'bg-st-incomplete-soft text-st-incomplete',
    bar: 'bg-st-incomplete',
    pin: 'var(--st-incomplete-pin)',
    glyph: 'M9 6.5v3M9 11.6h.01', // exclamation
  },
  failed: {
    label: 'Failed',
    badge: 'bg-st-failed-soft text-st-failed',
    bar: 'bg-st-failed',
    pin: 'var(--st-failed-pin)',
    glyph: 'M7.4 7.4l3.2 3.2M10.6 7.4l-3.2 3.2', // cross
  },
  canceled: {
    label: 'Canceled',
    badge: 'bg-st-canceled-soft text-st-canceled',
    bar: 'bg-st-canceled',
    pin: 'var(--st-canceled-pin)',
    glyph: 'M7.4 10.6l3.2-3.2', // slash
  },
};

/** Statuses a dispatcher may still cancel from (ADR-004 transition table). */
export const CANCELABLE: ReadonlySet<JobStatus> = new Set(['unassigned', 'assigned']);

export function isJobStatus(value: string): value is JobStatus {
  return (JOB_STATUSES as readonly string[]).includes(value);
}
