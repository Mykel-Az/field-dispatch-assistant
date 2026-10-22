import { describe, expect, it } from 'vitest';
import { ApiError } from './http';

describe('ApiError', () => {
  it('flattens nested serializer errors to plain field names', () => {
    const err = new ApiError(400, {
      technician: { non_field_errors: ['shift_end must be after shift_start.'] },
    });
    expect(err.fieldErrors).toEqual({
      non_field_errors: 'shift_end must be after shift_start.',
    });
    expect(err.message).toBe('shift_end must be after shift_start.');
  });

  it('keeps top-level field errors and the detail message', () => {
    expect(new ApiError(400, { email: ['Email unavailable.'] }).fieldErrors).toEqual({
      email: 'Email unavailable.',
    });
    const err = new ApiError(409, { detail: 'Someone else changed this.' });
    expect(err.message).toBe('Someone else changed this.');
    expect(err.fieldErrors).toEqual({});
  });

  it('never produces "[object Object]"', () => {
    const err = new ApiError(400, { technician: { skill_ids: ['Select at least one skill.'] } });
    expect(Object.values(err.fieldErrors).join(' ')).not.toContain('[object');
    expect(err.fieldErrors.skill_ids).toBe('Select at least one skill.');
  });

  it('falls back to a generic message for an empty body', () => {
    expect(new ApiError(500, null).message).toBe('Request failed (500)');
  });
});