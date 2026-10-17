export const ui = {
  page: 'min-h-screen bg-slate-100 text-slate-900',
  card: 'rounded-lg border border-slate-200 bg-white p-6 shadow-sm',
  cardNarrow: 'mx-auto mt-16 w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm',
  form: 'grid gap-4',
  label: 'grid gap-1 text-sm font-medium text-slate-700',
  input:
    'rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:bg-slate-100 disabled:text-slate-500',
  btn: 'rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:cursor-default disabled:opacity-60',
  btnSmall: 'rounded-md border border-slate-300 bg-white px-3 py-1 text-sm hover:bg-slate-50',
  error: 'text-sm font-normal text-red-700',
  muted: 'text-sm text-slate-500',
  notice: 'rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm',
  centerNote: 'mt-16 text-center text-slate-500',
  h1: 'mb-4 text-2xl font-semibold',
  h2: 'mb-3 mt-8 text-lg font-semibold',
  row: 'flex flex-wrap gap-4 [&>label]:min-w-36 [&>label]:flex-1',
} as const;