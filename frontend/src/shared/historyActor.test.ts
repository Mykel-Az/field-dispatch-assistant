import { describe, expect, it } from 'vitest';
import { historyActor } from './historyActor';

const person = { id: 1, full_name: 'Dana Reyes' };

describe('historyActor', () => {
  it('credits the planner, with the person who ran it in brackets', () => {
    expect(historyActor({ source: 'planner', changed_by: person })).toBe('Planner (run by Dana Reyes)');
  });
  it('credits a person for what they did by hand', () => {
    expect(historyActor({ source: 'manual', changed_by: person })).toBe('Dana Reyes');
  });
  it('says Planner when nobody ran it, and System for an unattributed manual row', () => {
    expect(historyActor({ source: 'planner', changed_by: null })).toBe('Planner');
    expect(historyActor({ source: 'manual', changed_by: null })).toBe('System');
  });
});
