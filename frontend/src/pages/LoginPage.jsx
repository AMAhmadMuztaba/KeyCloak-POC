import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();

  return (
    <div className="full-center">
      <div className="login-card">
        <div className="login-icon">🔐</div>
        <h1 className="login-title">KeyCLOAK App</h1>
        <p className="login-subtitle">
          Sign in to access your organisations and projects.
        </p>

        <button className="btn btn-primary btn-lg" onClick={login}>
          Sign in with Keycloak
        </button>

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
