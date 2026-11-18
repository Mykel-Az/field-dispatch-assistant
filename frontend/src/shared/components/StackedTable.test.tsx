// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { HeadCell, StackedBody, StackedCell, StackedHead, StackedRow, StackedTable } from './StackedTable';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root;
let host: HTMLElement;
beforeEach(() => {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

describe('StackedTable', () => {
  it('stays a table for assistive technology, and each cell carries its column name for the phone layout', () => {
    act(() => {
      root.render(
        <StackedTable label="Team">
          <StackedHead>
            <HeadCell>Name</HeadCell>
            <HeadCell />
          </StackedHead>
          <StackedBody>
            <StackedRow muted>
              <StackedCell label="Name">Ada</StackedCell>
              <StackedCell actions>
                <button>Edit</button>
              </StackedCell>
            </StackedRow>
          </StackedBody>
        </StackedTable>,
      );
    });
    expect(host.querySelector('table')!.getAttribute('role')).toBe('table');
    expect(host.querySelector('table')!.getAttribute('aria-label')).toBe('Team');
    expect([...host.querySelectorAll('[role="row"]')]).toHaveLength(2);
    const cells = [...host.querySelectorAll('[role="cell"]')];
    expect(cells[0].getAttribute('data-label')).toBe('Name');
    expect(cells[1].hasAttribute('data-label')).toBe(false); // the actions cell has no label
    expect(host.querySelector('tbody tr')!.className).toContain('text-ink-muted'); // muted row
  });
});
