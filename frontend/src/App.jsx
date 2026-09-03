import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import LoginPage from "./pages/LoginPage";
import OrgSelectPage from "./pages/OrgSelectPage";
import ProjectSelectPage from "./pages/ProjectSelectPage";
import DashboardPage from "./pages/DashboardPage";
import SuperAdminDashboard from "./pages/SuperAdminDashboard";
import OrgAdminDashboard from "./pages/OrgAdminDashboard";
import ProjectAdminDashboard from "./pages/ProjectAdminDashboard";
import SecurityPage from "./pages/SecurityPage";

function Spinner() {
  return (
    <div className="full-center">
      <div className="spinner" />
      <p className="text-muted" style={{ marginTop: "1rem" }}>
        Connecting to Keycloak…
      </p>
    </div>
  );
}

function AppRoutes() {
  const {
    isAuthenticated,
    selectedOrg,
    selectedProject,
    isAdminMode,
    isSuperAdmin,
    orgAdminOf,
    projectAdminOf,
    getAdminRoute,
  } = useAuth();

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    );
  }

  // Admin routes are always accessible regardless of org/project selection
  const adminRoutes = (
    <>
      {isSuperAdmin && (
        <Route path="/super-admin" element={<SuperAdminDashboard />} />
      )}
      {(isSuperAdmin || orgAdminOf.length > 0) && (
        <Route path="/org-admin" element={<OrgAdminDashboard />} />
      )}
      {(isSuperAdmin || orgAdminOf.length > 0 || projectAdminOf.length > 0) && (
        <Route path="/project-admin" element={<ProjectAdminDashboard />} />
      )}
    </>
  );

  if (!selectedOrg) {
    // Super admins with no org membership can jump straight to their dashboard
    if (isSuperAdmin && orgAdminOf.length === 0) {
      return (
        <Routes>
          <Route path="/select-org"   element={<OrgSelectPage />} />
          <Route path="/super-admin"  element={<SuperAdminDashboard />} />
          <Route path="*" element={<Navigate to="/super-admin" replace />} />
        </Routes>
      );
    }
    return (
      <Routes>
        {adminRoutes}
        <Route path="/select-org" element={<OrgSelectPage />} />
        <Route path="*" element={<Navigate to="/select-org" replace />} />
      </Routes>
    );
  }

  if (!selectedProject && !isAdminMode) {
    return (
      <Routes>
        {adminRoutes}
        <Route path="/select-org"     element={<OrgSelectPage />} />
        <Route path="/select-project" element={<ProjectSelectPage />} />
        <Route path="*" element={<Navigate to="/select-project" replace />} />
      </Routes>
    );
  }

  const defaultRoute = isAdminMode ? getAdminRoute() : "/dashboard";

  return (
    <Routes>
      {adminRoutes}
      <Route path="/select-org"     element={<OrgSelectPage />} />
      <Route path="/select-project" element={<ProjectSelectPage />} />
      <Route path="/dashboard"      element={<DashboardPage />} />
      <Route path="/security"       element={<SecurityPage />} />
      <Route path="/"  element={<Navigate to={defaultRoute} replace />} />
      <Route path="*"  element={<Navigate to={defaultRoute} replace />} />
    </Routes>
  );
}

export default function App() {
  const { isLoading, isAuthenticated } = useAuth();
  if (isLoading) return <Spinner />;

  return (
    <div className="app-shell">
      {isAuthenticated && <Navbar />}
      <main className="main-content">
        <AppRoutes />
      </main>
    </div>
  );
}
