import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../api";

const METHODS = [
  {
    key:    "totp",
    icon:   "📱",
    label:  "Authenticator App",
    desc:   "Google Authenticator, Authy, or Microsoft Authenticator",
    action: "CONFIGURE_TOTP",
    single: true,
  },
  {
    key:    "webauthn",
    icon:   "🔑",
    label:  "Security Key",
    desc:   "YubiKey or any FIDO2 hardware key",
    action: "webauthn-register",
    single: false,
  },
  {
    key:    "passkeys",
    icon:   "🛡",
    label:  "Passkey",
    desc:   "Touch ID, Face ID, or Windows Hello",
    action: "webauthn-register-passwordless",
    single: false,
  },
];

export default function SecurityPage() {
  const { setupMfa } = useAuth();
  const navigate = useNavigate();
  const [status,   setStatus]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [removing, setRemoving] = useState(null);
  const [removeError, setRemoveError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/api/user/mfa-status");
      setStatus(data);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function remove(credentialId) {
    setRemoving(credentialId);
    setRemoveError(null);
    try {
      await apiFetch(`/api/user/mfa/${credentialId}`, "DELETE");
      await load();
    } catch (e) {
      setRemoveError(e.message || "Failed to remove credential");
    } finally {
      setRemoving(null);
    }
  }

  function isConfigured(key) {
    if (!status) return false;
    if (key === "totp") return status.totp;
    return (status[key] || []).length > 0;
  }

  function credentials(key) {
    if (key === "totp") return status?.totp ? [{ id: "totp", label: "Authenticator App" }] : [];
    return status?.[key] || [];
  }

  return (
    <div className="page-container">
      <div className="security-page-header">
        <button className="btn btn-secondary btn-sm" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <div>
          <h2 className="page-title">Security Settings</h2>
          <p className="page-subtitle">Manage your two-factor authentication methods.</p>
        </div>
      </div>

      {removeError && (
        <div className="alert alert-error" role="alert">
          {removeError}
          <button className="alert-dismiss" onClick={() => setRemoveError(null)}>✕</button>
        </div>
      )}

      {loading ? (
        <div className="security-loading">Loading…</div>
      ) : (
        <div className="security-methods">
          {METHODS.map(m => {
            const configured = isConfigured(m.key);
            const creds      = credentials(m.key);
            return (
              <div key={m.key} className={`security-method-card ${configured ? "is-configured" : ""}`}>
                <div className="security-method-icon">{m.icon}</div>
                <div className="security-method-body">
                  <div className="security-method-top">
                    <div>
                      <div className="security-method-label">{m.label}</div>
                      <div className="security-method-desc">{m.desc}</div>
                    </div>
                    <span className={`security-badge ${configured ? "badge-on" : "badge-off"}`}>
                      {configured ? "Configured" : "Not set up"}
                    </span>
                  </div>

                  {creds.length > 0 && !m.single && (
                    <ul className="security-cred-list">
                      {creds.map(c => (
                        <li key={c.id} className="security-cred-item">
                          <span>{c.label}</span>
                          <button
                            className="btn-cred-remove"
                            disabled={removing === c.id}
                            onClick={() => remove(c.id)}
                          >
                            {removing === c.id ? "Removing…" : "Remove"}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="security-method-actions">
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => setupMfa(m.action)}
                    >
                      {configured ? (m.single ? "Update" : "+ Add another") : "Set up"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
