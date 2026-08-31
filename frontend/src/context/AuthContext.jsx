import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import keycloak from "../keycloak";

const AuthContext = createContext(null);

// ── Parse JWT groups into org/project memberships + admin roles ──────────────
function parseGroups(groups = []) {
  const parts = (g) => g.split("/").filter(Boolean);

  // Depth-1 groups = org memberships
  const orgs = [...new Set(
    groups.filter(g => parts(g).length === 1).map(g => parts(g)[0])
  )];

  // Depth-2 groups that are not 'admins' = project memberships
  const projectsForOrg = (org) =>
    groups
      .filter(g => parts(g).length === 2 && parts(g)[0] === org && parts(g)[1] !== "admins")
      .map(g => parts(g)[1]);

  // Depth-2 'admins' subgroup = org-admin role for that org
  const orgAdminOf = [...new Set(
    groups
      .filter(g => parts(g).length === 2 && parts(g)[1] === "admins")
      .map(g => parts(g)[0])
  )];

  // Depth-3 'admins' subgroup = project-admin role for that project
  const projectAdminOf = groups
    .filter(g => parts(g).length === 3 && parts(g)[2] === "admins")
    .map(g => ({ org: parts(g)[0], project: parts(g)[1] }));

  return { orgs, projectsForOrg, orgAdminOf, projectAdminOf };
}

// ── Provider ──────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [isLoading, setIsLoading]             = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [tokenParsed, setTokenParsed]         = useState(null);
  const [selectedOrg, setSelectedOrg]         = useState(
    () => sessionStorage.getItem("kc_org") || null
  );
  const [selectedProject, setSelectedProject] = useState(
    () => sessionStorage.getItem("kc_project") || null
  );
  const [isAdminMode, setIsAdminMode]         = useState(
    () => sessionStorage.getItem("kc_admin_mode") === "true"
  );
  const initCalled = useRef(false);

  useEffect(() => {
    if (initCalled.current) return;
    initCalled.current = true;

    keycloak
      .init({
        onLoad: "check-sso",
        silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      })
      .then((authenticated) => {
        setIsAuthenticated(authenticated);
        if (authenticated) setTokenParsed(keycloak.tokenParsed);
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));

    keycloak.onTokenExpired = () => {
      keycloak.updateToken(30).catch(() => {
        setIsAuthenticated(false);
        setTokenParsed(null);
      });
    };
  }, []);

  const login  = useCallback(() => keycloak.login(), []);
  const logout = useCallback(() => {
    sessionStorage.clear();
    keycloak.logout({ redirectUri: window.location.origin });
  }, []);

  const selectOrg = useCallback((org) => {
    setSelectedOrg(org);
    setSelectedProject(null);
    setIsAdminMode(false);
    sessionStorage.setItem("kc_org", org);
    sessionStorage.removeItem("kc_project");
    sessionStorage.removeItem("kc_admin_mode");
  }, []);

  const selectProject = useCallback((project) => {
    setSelectedProject(project);
    setIsAdminMode(false);
    sessionStorage.setItem("kc_project", project);
    sessionStorage.removeItem("kc_admin_mode");
  }, []);

  const enterAdminMode = useCallback(() => {
    setIsAdminMode(true);
    setSelectedProject(null);
    sessionStorage.setItem("kc_admin_mode", "true");
    sessionStorage.removeItem("kc_project");
  }, []);

  const { orgs, projectsForOrg, orgAdminOf, projectAdminOf } = useMemo(
    () => parseGroups(tokenParsed?.groups),
    [tokenParsed]
  );

  const isSuperAdmin = useMemo(
    () => (tokenParsed?.realm_access?.roles || []).includes("super-admin"),
    [tokenParsed]
  );

  const isOrgAdminOf = useCallback(
    (org) => isSuperAdmin || orgAdminOf.includes(org),
    [isSuperAdmin, orgAdminOf]
  );

  const isProjectAdminOf = useCallback(
    (org, project) =>
      isSuperAdmin ||
      orgAdminOf.includes(org) ||
      projectAdminOf.some(p => p.org === org && p.project === project),
    [isSuperAdmin, orgAdminOf, projectAdminOf]
  );

  // Which admin dashboard to navigate to when "Skip" is clicked
  const getAdminRoute = useCallback(() => {
    if (isSuperAdmin)        return "/super-admin";
    if (orgAdminOf.length)   return "/org-admin";
    if (projectAdminOf.length) return "/project-admin";
    return "/dashboard";
  }, [isSuperAdmin, orgAdminOf, projectAdminOf]);

  const hasAnyAdminRole = isSuperAdmin || orgAdminOf.length > 0 || projectAdminOf.length > 0;

  const user = useMemo(
    () =>
      tokenParsed
        ? {
            sub:       tokenParsed.sub,
            username:  tokenParsed.preferred_username,
            email:     tokenParsed.email,
            firstName: tokenParsed.given_name,
            lastName:  tokenParsed.family_name,
          }
        : null,
    [tokenParsed]
  );

  const value = {
    isLoading,
    isAuthenticated,
    user,
    // roles
    isSuperAdmin,
    orgAdminOf,
    projectAdminOf,
    isOrgAdminOf,
    isProjectAdminOf,
    hasAnyAdminRole,
    getAdminRoute,
    // groups
    orgs,
    projectsForOrg,
    // selection state
    selectedOrg,
    selectedProject,
    isAdminMode,
    // actions
    login,
    logout,
    selectOrg,
    selectProject,
    enterAdminMode,
    token: keycloak.token,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
};
