import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import AdminShell from "./components/AdminShell";
import OrganisationsPage from "./pages/OrganisationsPage";
import OrgDetailPage from "./pages/OrgDetailPage";
import UsersPage from "./pages/UsersPage";
import UserDetailPage from "./pages/UserDetailPage";
import RolesPage from "./pages/RolesPage";

function Spinner() {
  return (
    <div className="full-center">
      <div className="spinner" />
    </div>
  );
}

function AccessDenied() {
  const { logout } = useAuth();
  return (
    <div className="full-center">
      <div className="access-denied-card">
        <h2>Access denied</h2>
        <p>This portal requires the <strong>super-admin</strong> role.</p>
        <button className="btn btn-secondary" onClick={logout}>Sign out</button>
      </div>
    </div>
  );
}

export default function App() {
  const { isLoading, isSuperAdmin } = useAuth();

  if (isLoading)    return <Spinner />;
  if (!isSuperAdmin) return <AccessDenied />;

  return (
    <Routes>
      <Route element={<AdminShell />}>
        <Route index element={<Navigate to="/organisations" replace />} />
        <Route path="organisations"       element={<OrganisationsPage />} />
        <Route path="organisations/:org/*" element={<OrgDetailPage />} />
        <Route path="users"               element={<UsersPage />} />
        <Route path="users/:userId"       element={<UserDetailPage />} />
        <Route path="roles"               element={<RolesPage />} />
        <Route path="*"                   element={<Navigate to="/organisations" replace />} />
      </Route>
    </Routes>
  );
}
