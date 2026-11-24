import { formatStamp, splitLocal } from './jobTime';

/** What an edit row says changed: one line per field, "Priority: Normal → High". */
export interface EditLine {
  field: string;
  label: string;
  from: string;
  to: string;
}

const LABELS: Record<string, string> = {
  title: 'Title',
  description: 'Description',
  category: 'Category',
  customer_name: 'Customer',
  customer_phone: 'Phone',
  address: 'Address',
  postal_code: 'ZIP',
  location: 'Location',
  priority: 'Priority',
  is_urgent: 'Urgent',
  slot_start: 'Window start',
  slot_end: 'Window end',
  scheduled_date: 'Day',
  slot_is_fixed: 'Time is fixed',
  estimated_duration_minutes: 'Duration (min)',
  skills: 'Skills',
};

const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MAX = 60;

function shorten(text: string): string {
  return text.length > MAX ? `${text.slice(0, MAX).trimEnd()}…` : text;
}

/** One stored value as a person would read it. */
export function editValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return 'empty';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.length === 0 ? 'none' : value.join(', ');
  if (typeof value === 'string') {
    if (ISO_DATETIME.test(value)) return formatStamp(value);
    if (ISO_DATE.test(value)) return splitLocal(`${value}T12:00:00Z`).date;
    if (field === 'priority' || field === 'category')
      return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ');
    return shorten(value);
  }
  return String(value);
}

/** Two long texts, each cut to a window that starts just before where they differ, so
 *  "Unit blowing warm air… → Unit blowing warm air…" still shows what changed. */
function windowAround(a: string, b: string): [string, string] {
  if (a.length <= MAX && b.length <= MAX) return [a, b];
  let same = 0;
  while (same < a.length && same < b.length && a[same] === b[same]) same += 1;
  const start = Math.max(0, same - 15);
  const cut = (t: string) =>
    (start > 0 ? '…' : '') + t.slice(start, start + MAX) + (t.length > start + MAX ? '…' : '');
  return [cut(a), cut(b)];
}

/** The lines for an edit row's `changes`, tolerating anything the server may add later. */
export function editLines(changes: unknown): EditLine[] {
  if (!changes || typeof changes !== 'object') return [];
  const lines: EditLine[] = [];
  for (const [field, pair] of Object.entries(changes as Record<string, unknown>)) {
    if (!Array.isArray(pair) || pair.length !== 2) continue;
    const longText = typeof pair[0] === 'string' && typeof pair[1] === 'string' && !ISO_DATETIME.test(pair[0]);
    const [from, to] = longText
      ? windowAround(pair[0] as string, pair[1] as string)
      : [editValue(field, pair[0]), editValue(field, pair[1])];
    lines.push({
      field,
      label: LABELS[field] ?? field.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()),
      from: from === '' ? 'empty' : field === 'priority' || field === 'category' ? editValue(field, from) : from,
      to: to === '' ? 'empty' : field === 'priority' || field === 'category' ? editValue(field, to) : to,
    });
  }
  return lines;
}
