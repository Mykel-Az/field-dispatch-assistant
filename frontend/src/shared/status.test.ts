import { describe, expect, it } from 'vitest';
import { CANCELABLE, isJobStatus, JOB_STATUSES, STATUS_META } from './status';

describe('job statuses', () => {
  it('has display data for all seven statuses', () => {
    expect(JOB_STATUSES).toHaveLength(7);
    for (const s of JOB_STATUSES) {
      expect(STATUS_META[s].label.length).toBeGreaterThan(0);
      expect(STATUS_META[s].badge).toContain(`st-${s}`);
    }
  });

  it('gives every status its own pin colour and glyph, so none look alike', () => {
    const pins = JOB_STATUSES.map((s) => STATUS_META[s].pin);
    const glyphs = JOB_STATUSES.map((s) => STATUS_META[s].glyph);
    expect(new Set(pins).size).toBe(7);
    expect(new Set(glyphs).size).toBe(7);
  });

  it('matches the cancel rule in the transition table', () => {
    expect([...CANCELABLE].sort()).toEqual(['assigned', 'unassigned']);
  });

  it('recognises only real statuses', () => {
    expect(isJobStatus('ongoing')).toBe(true);
    expect(isJobStatus('paused')).toBe(false);
  });
});
