// What the plan page shows, worked out from the API result. Pure functions, so
// they are easy to test and the page stays a thin layer of markup.
import type { PlanReason, PlannedJob, Technician } from '../../shared/api/models';
import { splitLocal } from '../../shared/jobTime';

/** The server speaks in ids; these are the names it can be matched to. */
export interface TechnicianPlan {
  technicianId: number;
  name: string;
  /** "08:00–17:00", or '' when the technician is not in the loaded list. */
  shift: string;
  /** In the order the technician drives them. */
  stops: PlannedJob[];
}

const hhmm = (t: string) => t.slice(0, 5);

/** Group assigned jobs by technician: people A to Z, each person's stops by arrival. */
export function groupByTechnician(
  assigned: PlannedJob[],
  technicians: Technician[],
): TechnicianPlan[] {
  const byId = new Map(technicians.map((t) => [t.id, t]));
  const groups = new Map<number, TechnicianPlan>();
  for (const stop of assigned) {
    let group = groups.get(stop.technician_id);
    if (!group) {
      const tech = byId.get(stop.technician_id);
      group = {
        technicianId: stop.technician_id,
        name: tech?.user.full_name ?? `Technician #${stop.technician_id}`,
        shift: tech ? `${hhmm(tech.shift_start)}–${hhmm(tech.shift_end)}` : '',
        stops: [],
      };
      groups.set(stop.technician_id, group);
    }
    group.stops.push(stop);
  }
  const plans = [...groups.values()];
  plans.forEach((p) =>
    p.stops.sort((a, b) => a.estimated_arrival.localeCompare(b.estimated_arrival)),
  );
  return plans.sort((a, b) => a.name.localeCompare(b.name));
}

export type SlaKey = 'ok' | 'at_risk' | 'breach';
export interface SlaMeta {
  label: string;
  /** A glyph, so the state is not carried by colour alone. */
  mark: string;
  classes: string;
}

const SLA: Record<SlaKey, SlaMeta> = {
  ok: { label: 'On time', mark: '✓', classes: 'bg-st-completed-soft text-st-completed' },
  at_risk: { label: 'At risk', mark: '!', classes: 'bg-warn-soft text-warn-ink' },
  breach: { label: 'Late', mark: '✕', classes: 'bg-danger-soft text-danger' },
};

/** False for a plan saved before the SLA was stored with it: show no badge then. */
export const hasSla = (label: string): label is SlaKey => label in SLA;

export function slaMeta(label: string): SlaMeta {
  return SLA[label as SlaKey] ?? { label, mark: '?', classes: 'bg-canvas text-ink-muted' };
}

/** "48 min to spare" or "7 min late", rounded the same way as the sentence. */
export function slackText(slackMinutes: number): string {
  const whole = Math.floor(slackMinutes);
  return whole < 0 ? `${-whole} min late` : `${whole} min to spare`;
}

/** "09:12" on the organization's clock. */
export const arrivalTime = (iso: string, tz?: string) => splitLocal(iso, tz).time;

/** One line for the top of the results. */
export function summaryLine(counts: {
  assigned: number;
  technicians: number;
  unassigned: number;
  skipped: number;
}): string {
  const jobs = (n: number) => `${n} job${n === 1 ? '' : 's'}`;
  const parts: string[] = [];
  if (counts.assigned > 0) {
    parts.push(
      `Planned ${jobs(counts.assigned)} across ${counts.technicians} technician${
        counts.technicians === 1 ? '' : 's'
      }`,
    );
  }
  if (counts.unassigned > 0) parts.push(`${jobs(counts.unassigned)} could not be assigned`);
  if (counts.skipped > 0) {
    parts.push(`${jobs(counts.skipped)} ${counts.skipped === 1 ? 'needs' : 'need'} a location`);
  }
  return parts.join(' · ');
}

const REJECTION_TEXT: Record<string, (facts: Record<string, unknown>) => string> = {
  unavailable: () => 'is unavailable',
  skill_mismatch: () => 'does not have a matching skill',
  daily_limit: (f) => `has reached the daily limit of ${String(f.limit)} jobs`,
  after_closing: (f) => `would arrive ${String(f.minutes_after_closing)} min after closing`,
};

/**
 * The "why not the others?" lines: one per technician the planner passed over,
 * for example "Alex is unavailable". Codes that explain the choice itself are
 * left to the sentence.
 */
export function rejectionLines(reasons: PlanReason[], technicians: Technician[]): string[] {
  const names = new Map(technicians.map((t) => [t.id, t.user.full_name]));
  const lines: string[] = [];
  for (const reason of reasons) {
    const text = REJECTION_TEXT[reason.code];
    if (!text) continue;
    const facts = reason.facts as Record<string, unknown>;
    const id = Number(facts.technician_id);
    lines.push(`${names.get(id) ?? `Technician #${id}`} ${text(facts)}`);
  }
  return lines;
}

/** "2026-11-08" plus `days`, calendar arithmetic only (no time zones involved). */
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number);
  const next = new Date(Date.UTC(y, m - 1, d + days));
  return next.toISOString().slice(0, 10);
}

/** Today's date on the organization's clock. */
export const todayOnClock = (tz?: string, now: Date = new Date()) =>
  splitLocal(now.toISOString(), tz).date;

/** The longest lookahead the API accepts (ADR-010). */
export const MAX_DAYS_AHEAD = 7;