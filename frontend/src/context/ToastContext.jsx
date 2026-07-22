import { createContext, useContext, useState, useCallback } from 'react';
import AIActionFeedback from '../components/AIActionFeedback';

// ─────────────────────────────────────────────────────────
//  ToastContext — lifts the Undo-toast queue that used to live
//  inside Dashboard so any page (or the chat assistant) can push
//  a toast regardless of which route is currently mounted.
// ─────────────────────────────────────────────────────────

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const pushToast = useCallback((toast) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setToasts((prev) => [...prev, { id, kind: 'success', undoable: false, ...toast }]);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ pushToast }}>
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <AIActionFeedback key={t.id} toast={t} onDone={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
