import { describe, expect, it } from 'vitest';
import { editLines, editValue } from './historyEdits';

describe('editLines', () => {
  it('names each changed field with its old and new value', () => {
    expect(editLines({ priority: ['normal', 'high'], is_urgent: [false, true] })).toEqual([
      { field: 'priority', label: 'Priority', from: 'Normal', to: 'High' },
      { field: 'is_urgent', label: 'Urgent', from: 'No', to: 'Yes' },
    ]);
  });

  it('lists skills by name and shows an empty value as "empty"', () => {
    const [skills, phone] = editLines({ skills: [['HVAC'], ['Electrical', 'HVAC']], customer_phone: ['', '5125550100'] });
    expect([skills.from, skills.to]).toEqual(['HVAC', 'Electrical, HVAC']);
    expect([phone.from, phone.to]).toEqual(['empty', '5125550100']);
  });

  it('shortens long text so one edit does not fill the page', () => {
    const long = 'x'.repeat(200);
    const [line] = editLines({ description: ['short', long] });
    expect(line.to.length).toBeLessThanOrEqual(61);
    expect(line.to.endsWith('…')).toBe(true);
  });

  it('cuts long text at the place it changed, so the change is visible', () => {
    const base = 'Unit blowing warm air since last night. Elderly resident at home, please hurry.';
    const [line] = editLines({ description: [base, `${base} Customer asked for a callback.`] });
    expect(line.from).not.toBe(line.to);
    expect(line.to).toContain('callback');
  });

  it('shows a time the way the rest of the app does, never as raw ISO text', () => {
    const shown = editValue('slot_start', '2026-11-23T20:00:00+00:00');
    expect(shown).toMatch(/Nov 23/);
    expect(shown).not.toContain('T20');
    expect(editValue('scheduled_date', '2026-11-23')).toBe('2026-11-23');
  });

  it('survives a field it does not know and ignores a malformed entry', () => {
    expect(editLines({ new_thing: ['a', 'b'], broken: 'nope', also: [1] })).toEqual([
      { field: 'new_thing', label: 'New thing', from: 'a', to: 'b' },
    ]);
    expect(editLines(null)).toEqual([]);
    expect(editLines('x')).toEqual([]);
  });
});
