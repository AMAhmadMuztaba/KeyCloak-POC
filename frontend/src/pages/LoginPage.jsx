import { useAuth } from "../context/AuthContext";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#F25022" d="M1 1h10v10H1z"/>
      <path fill="#7FBA00" d="M13 1h10v10H13z"/>
      <path fill="#00A4EF" d="M1 13h10v10H1z"/>
      <path fill="#FFB900" d="M13 13h10v10H13z"/>
    </svg>
  );
}

export default function LoginPage() {
  const { login, loginWithIdp } = useAuth();

  return (
    <div className="full-center">
      <div className="login-card">
        <div className="login-icon">🔐</div>
        <h1 className="login-title">KeyCLOAK App</h1>
        <p className="login-subtitle">
          Sign in to access your organisations and projects.
        </p>

        <button className="btn btn-primary btn-lg" style={{ width: "100%" }} onClick={login}>
          Sign in with Keycloak
        </button>

        <div className="login-divider"><span>or continue with</span></div>

        <div className="social-buttons">
          <button className="btn-social" onClick={() => loginWithIdp("google")}>
            <GoogleIcon />
            Google
          </button>
          <button className="btn-social" onClick={() => loginWithIdp("microsoft")}>
            <MicrosoftIcon />
            Microsoft
          </button>
        </div>

        <div className="mfa-strip">
          <span className="mfa-strip-item">🔑 TOTP</span>
          <span className="mfa-strip-sep">·</span>
          <span className="mfa-strip-item">🛡 WebAuthn</span>
          <span className="mfa-strip-sep">·</span>
          <span className="mfa-strip-item">📱 Passkeys</span>
        </div>

        <div className="login-hint">
          <p>Demo accounts</p>
          <table className="demo-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Password</th>
                <th>Access</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>alice</td>
                <td>alice123</td>
                <td><span className="role-badge role-super">Super Admin</span></td>
              </tr>
              <tr>
                <td>bob</td>
                <td>bob123</td>
                <td><span className="role-badge role-org">Org Admin</span></td>
              </tr>
              <tr>
                <td>carol</td>
                <td>carol123</td>
                <td><span className="role-badge role-project">Project Admin</span></td>
              </tr>
              <tr>
                <td>dave</td>
                <td>dave123</td>
                <td><span className="badge badge-user">User</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
