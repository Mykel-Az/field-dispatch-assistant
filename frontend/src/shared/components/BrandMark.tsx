/** The app's logo: the same teal map-pin tile as public/favicon.svg, in design tokens. */
export function BrandMark({ className = 'size-16' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="9" className="fill-brand" />
      <path
        d="M16 6c-4.1 0-7.2 3-7.2 7 0 5.2 7.2 12.5 7.2 12.5s7.2-7.3 7.2-12.5c0-4-3.1-7-7.2-7Z"
        className="fill-on-brand"
      />
      <circle cx="16" cy="13" r="2.8" className="fill-brand" />
    </svg>
  );
}
