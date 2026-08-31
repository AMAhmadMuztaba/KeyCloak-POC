import { memo, useCallback, useMemo, useState } from "react";

// Stable module-level component — never re-created, so React won't remount it
const ToastView = memo(function ToastView({ toasts }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span className="toast-icon">{t.type === "success" ? "✓" : "✕"}</span>
          {t.text}
        </div>
      ))}
    </div>
  );
});

export function useToast() {
  const [toasts, setToasts] = useState([]);

  const show = useCallback((text, type = "success") => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, text, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
  }, []);

  const toast = useMemo(() => ({
    success: (text) => show(text, "success"),
    error:   (text) => show(text, "error"),
  }), [show]);

  // Return rendered JSX (not a component reference) so React sees a stable element type
  const Toasts = <ToastView toasts={toasts} />;

  return { toast, Toasts };
}
