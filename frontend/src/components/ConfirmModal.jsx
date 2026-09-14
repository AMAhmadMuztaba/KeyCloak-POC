import { useEffect } from "react";

export default function ConfirmModal({ open, title, body, confirmLabel = "Confirm", isPending, onConfirm, onClose, danger }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-panel" role="dialog" aria-modal="true">
        <p className="modal-title">{title}</p>
        {body && <p className="modal-body">{body}</p>}
        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={isPending}>
            Cancel
          </button>
          <button
            className={`btn btn-sm ${danger ? "btn-danger" : "btn-primary"}`}
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "Please wait…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
