import type { ReactNode } from 'react';

// A table that is a table from 768px up and a stack of cards below that: each row
// becomes a card and each cell shows its column name beside the value. One markup,
// so there is no second list to keep in step. Explicit roles keep it a table for
// screen readers even while the browser lays it out as blocks.

export function StackedTable({ label, children }: { label: string; children: ReactNode }) {
  return (
    <table role="table" aria-label={label} className="block w-full border-collapse text-left text-sm md:table">
      {children}
    </table>
  );
}

/** Column names. Hidden on a phone, where every cell carries its own. */
export function StackedHead({ children }: { children: ReactNode }) {
  return (
    <thead role="rowgroup" className="hidden md:table-header-group">
      <tr role="row" className="border-b border-line text-ink-muted">
        {children}
      </tr>
    </thead>
  );
}

export function HeadCell({ children }: { children?: ReactNode }) {
  return (
    <th role="columnheader" className="p-2 font-semibold">
      {children}
    </th>
  );
}

export function StackedBody({ children }: { children: ReactNode }) {
  return (
    <tbody role="rowgroup" className="block md:table-row-group">
      {children}
    </tbody>
  );
}

export function StackedRow({ muted = false, children }: { muted?: boolean; children: ReactNode }) {
  return (
    <tr
      role="row"
      className={`mb-3 block rounded-xl border border-line p-2 md:mb-0 md:table-row md:rounded-none md:border-0 md:border-b md:p-0 ${muted ? 'text-ink-muted' : ''}`}
    >
      {children}
    </tr>
  );
}

/** `label` is the column name shown beside the value on a phone; leave it out for an actions cell. */
export function StackedCell({
  label,
  actions = false,
  children,
}: {
  label?: string;
  actions?: boolean;
  children?: ReactNode;
}) {
  return (
    <td
      role="cell"
      data-label={label}
      className={`flex items-start gap-3 px-2 py-1.5 md:table-cell md:p-2 ${
        label ? 'before:w-20 before:shrink-0 before:font-medium before:text-ink-muted before:content-[attr(data-label)] md:before:content-none' : ''
      } ${actions ? 'flex-wrap md:whitespace-nowrap md:text-right md:[&>*+*]:ml-2' : ''}`}
    >
      {children}
    </td>
  );
}
