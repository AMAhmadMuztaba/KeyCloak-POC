import { useEffect } from "react";
import { X } from "lucide-react";

export default function Drawer({ open, onClose, title, description, onSubmit, isPending, submitLabel = "Save", children }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="drawer-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer-panel" role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div>
            <p className="drawer-title">{title}</p>
            {description && <p className="drawer-desc">{description}</p>}
          </div>
          <button className="btn-ghost btn-ghost-sm" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <form
          onSubmit={onSubmit}
          style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}
        >
          <div className="drawer-body">{children}</div>
          <div className="drawer-foot">
            <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} disabled={isPending}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={isPending}>
              {isPending ? "Saving…" : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
