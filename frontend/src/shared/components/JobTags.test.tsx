// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import JobTags from './JobTags';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function render(job: Parameters<typeof JobTags>[0]['job']) {
  const host = document.createElement('div');
  const root = createRoot(host);
  act(() => root.render(<JobTags job={job} />));
  return host.textContent ?? '';
}

describe('JobTags', () => {
  it('shows nothing for an ordinary job, so a tag means something', () => {
    expect(render({ priority: 'normal', slot_is_fixed: true })).toBe('');
    expect(render(undefined)).toBe('');
  });
  it('labels high and low priority', () => {
    expect(render({ priority: 'high', slot_is_fixed: true })).toBe('High priority');
    expect(render({ priority: 'low', slot_is_fixed: true })).toBe('Low priority');
  });
  it('labels a job with no agreed time, alongside its priority', () => {
    expect(render({ priority: 'normal', slot_is_fixed: false })).toBe('Any time');
    expect(render({ priority: 'high', slot_is_fixed: false })).toBe('High priorityAny time');
  });
});
