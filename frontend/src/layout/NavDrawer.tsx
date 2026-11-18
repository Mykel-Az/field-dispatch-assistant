import { useEffect, useRef } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface Props {
  onClose: () => void;
  children: React.ReactNode;
}

/**
 * The navigation panel for screens below the sidebar breakpoint. While it is open:
 * focus moves into it and Tab / Shift+Tab stay inside, Escape and a tap on the dim
 * area close it, the page behind does not scroll, and focus goes back to the button
 * that opened it when it closes. It is only rendered while open.
 */
export default function NavDrawer({ onClose, children }: Props) {
  const panel = useRef<HTMLDivElement>(null);
  const closing = useRef(onClose);
  useEffect(() => {
    closing.current = onClose;
  });

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panel.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    return () => {
      document.body.style.overflow = overflow;
      opener?.focus?.();
    };
  }, []);

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      e.stopPropagation();
      closing.current();
      return;
    }
    if (e.key !== 'Tab' || !panel.current) return;
    const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] lg:hidden" onKeyDown={onKeyDown}>
      <div aria-hidden="true" className="absolute inset-0 bg-ink/60" onClick={() => closing.current()} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
        className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col gap-4 overflow-y-auto bg-surface p-4 shadow-xl"
      >
        {children}
      </div>
    </div>
  );
}
