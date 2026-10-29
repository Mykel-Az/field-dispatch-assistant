import { STATUS_META, type JobStatus } from '../status';

/** Map-pin shape in the status colour, with the status glyph in the centre. */
export default function StatusPin({ status, size = 24 }: { status: JobStatus; size?: number }) {
  const meta = STATUS_META[status];
  return (
    <svg
      width={(size * 18) / 22}
      height={size}
      viewBox="0 0 18 22"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M9 1C4.6 1 1 4.5 1 8.8c0 5.6 8 12.2 8 12.2s8-6.6 8-12.2C17 4.5 13.4 1 9 1Z"
        style={{ fill: meta.pin }}
        // Dark outline: keeps every pin readable (3:1) on pale map tiles, even the light orange.
        stroke="#2a2622"
        strokeWidth="1"
      />
      <circle cx="9" cy="9" r="4.6" fill="#fff" />
      <path
        d={meta.glyph}
        fill="none"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ stroke: meta.pin }}
      />
    </svg>
  );
}
