// Shared class strings. Colours come from the tokens in index.css, never raw
// hex or slate/blue utilities, so a theme change (or dark mode) is one place.
export const ui = {
  page: 'min-h-screen bg-canvas text-ink',
  card: 'rounded-card border border-line bg-surface p-6 shadow-sm',
  cardNarrow:
    'mx-auto mt-16 w-full max-w-sm rounded-card border border-line bg-surface p-6 shadow-sm',
  form: 'grid gap-4',
  label: 'grid gap-1 text-sm font-medium text-ink-muted',
  input:
    'min-h-11 rounded-xl border-[1.5px] border-line-strong bg-surface px-3 py-2 text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30 disabled:bg-canvas disabled:text-ink-muted',
  btn: 'min-h-11 rounded-full bg-brand px-5 py-2 font-semibold text-on-brand shadow-sm hover:bg-brand-hover disabled:cursor-default disabled:opacity-60',
  btnSmall:
    'min-h-11 rounded-full border-[1.5px] border-line-strong bg-surface px-4 py-1 text-sm font-semibold hover:bg-canvas disabled:cursor-default disabled:opacity-60',
  btnDanger:
    'min-h-11 rounded-full border-[1.5px] border-danger bg-surface px-4 py-1 text-sm font-semibold text-danger hover:bg-danger-soft disabled:cursor-default disabled:opacity-60',
  error: 'text-sm font-normal text-danger',
  muted: 'text-sm text-ink-muted',
  notice: 'rounded-xl border border-warn-ink/30 bg-warn-soft px-3 py-2 text-sm text-warn-ink',
  centerNote: 'mt-16 text-center text-ink-muted',
  h1: 'mb-4 text-3xl font-bold tracking-tight',
  h2: 'mb-3 mt-8 text-lg font-bold',
  row: 'flex flex-wrap gap-4 [&>label]:min-w-36 [&>label]:flex-1',
  chip: 'rounded-full bg-brand-soft px-3 py-1 text-sm font-medium text-brand-ink',
  flag: 'inline-flex items-center gap-1.5 rounded-full bg-warn-soft px-3 py-0.5 text-sm font-bold text-warn-ink',
} as const;
