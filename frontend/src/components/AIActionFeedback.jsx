import { useEffect, useRef, useState } from 'react';

const WINDOW_SECONDS = 10;

/**
 * AIActionFeedback — a single Undo toast for an AI- or user-triggered
 * mutation (ADD / EDIT / DELETE). Owns its own 10-second countdown.
 *
 * `toast` shape:
 *   {
 *     id: string,
 *     kind: 'success' | 'error',
 *     message: string,
 *     undoable: boolean,
 *     onUndo: () => void | Promise<void>,   // fires if the user clicks Undo in time
 *     onExpire: () => void | Promise<void>, // fires once the window elapses untouched
 *   }
 *
 * Whether `onUndo` reverses an already-committed write (chat ADD/EDIT/DELETE,
 * which the backend applies synchronously) or `onExpire` performs a write
 * that was deliberately deferred (manual inline delete) is entirely up to
 * the caller — this component only owns the timing and exactly-once firing.
 */
export default function AIActionFeedback({ toast, onDone }) {
  const [remaining, setRemaining] = useState(WINDOW_SECONDS);
  const settledRef = useRef(false);

  useEffect(() => {
    settledRef.current = false;
    setRemaining(WINDOW_SECONDS);

    const tick = setInterval(() => {
      setRemaining((r) => Math.max(0, r - 1));
    }, 1000);

    const timeout = setTimeout(async () => {
      if (settledRef.current) return;
      settledRef.current = true;
      try {
        await toast.onExpire?.();
      } catch (err) {
        console.error('AIActionFeedback: onExpire failed', err);
      }
      onDone();
    }, WINDOW_SECONDS * 1000);

    return () => {
      clearInterval(tick);
      clearTimeout(timeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast.id]);

  async function handleUndo() {
    if (settledRef.current) return;
    settledRef.current = true;
    try {
      await toast.onUndo?.();
    } catch (err) {
      console.error('AIActionFeedback: onUndo failed', err);
    }
    onDone();
  }

  return (
    <div className={`toast ${toast.kind || 'success'}`}>
      <span style={{ flex: 1 }}>{toast.message}</span>
      {toast.undoable && (
        <button
          type="button"
          className="toast-undo-btn"
          onClick={handleUndo}
        >
          Undo · {remaining}s
        </button>
      )}
    </div>
  );
}
