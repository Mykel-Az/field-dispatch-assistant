import { useBack } from '../useBack';

/** "← Back to plan / map / jobs": returns to wherever the person came from. */
export default function BackLink({ className = 'text-sm text-brand hover:underline' }: { className?: string }) {
  const { label, go } = useBack();
  return (
    <button type="button" onClick={go} className={`${className} min-h-11 text-left`}>
      {label}
    </button>
  );
}
