import { useEffect, useRef, useState } from "react";
import { useDebounce } from "../hooks/useDebounce";
import { apiFetch } from "../api";

/**
 * Reusable user-search widget.
 * Calls /api/admin/users (accessible to all admin roles).
 * Props:
 *   token    – Keycloak access token
 *   onSelect – fn(user) called when user is chosen
 *   exclude  – array of user IDs to hide (already-members)
 *   placeholder – input placeholder text
 */
export default function UserSearch({ token, onSelect, exclude = [], placeholder = "Search by username or email…" }) {
  const [query, setQuery]       = useState("");
  const [results, setResults]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [open, setOpen]         = useState(false);
  const debouncedQ              = useDebounce(query, 350);
  const wrapRef                 = useRef(null);

  useEffect(() => {
    if (!debouncedQ.trim()) { setResults([]); setOpen(false); return; }
    setLoading(true);
    apiFetch(`/api/admin/users?search=${encodeURIComponent(debouncedQ)}`, "GET", undefined, token)
      .then(d => {
        const filtered = (d.users || []).filter(u => !exclude.includes(u.id));
        setResults(filtered);
        setOpen(true);
      })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [debouncedQ]);

  // Close dropdown on outside click
  useEffect(() => {
    function handle(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  function select(user) {
    setQuery("");
    setResults([]);
    setOpen(false);
    onSelect?.(user);
  }

  return (
    <div className="user-search-wrap" ref={wrapRef}>
      <div className="user-search-input-row">
        <span className="search-icon">🔍</span>
        <input
          className="form-input"
          placeholder={placeholder}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          autoComplete="off"
        />
        {loading && <span className="search-spinner" />}
      </div>

      {open && results.length > 0 && (
        <div className="user-search-dropdown">
          {results.map(u => (
            <button
              key={u.id}
              className="user-search-option"
              onMouseDown={() => select(u)}
            >
              <span className="user-avatar">{(u.username?.[0] || "?").toUpperCase()}</span>
              <span className="user-option-info">
                <span className="user-option-name">{u.username}</span>
                <span className="user-option-email">{u.email}</span>
              </span>
            </button>
          ))}
        </div>
      )}

      {open && query && !loading && results.length === 0 && (
        <div className="user-search-dropdown user-search-empty">
          No users found for "{query}"
        </div>
      )}
    </div>
  );
}
