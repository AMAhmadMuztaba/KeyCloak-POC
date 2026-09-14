import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import keycloak from "../keycloak";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isLoading,       setIsLoading]       = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [tokenParsed,     setTokenParsed]     = useState(null);
  const initCalled = useRef(false);

  useEffect(() => {
    if (initCalled.current) return;
    initCalled.current = true;

    keycloak
      .init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false })
      .then((authenticated) => {
        setIsAuthenticated(authenticated);
        if (authenticated) setTokenParsed(keycloak.tokenParsed);
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));

    keycloak.onAuthRefreshSuccess = () => setTokenParsed({ ...keycloak.tokenParsed });
    keycloak.onTokenExpired = () => {
      keycloak.updateToken(30).catch(() => {
        setIsAuthenticated(false);
        setTokenParsed(null);
      });
    };
  }, []);

  const logout = useCallback(
    () => keycloak.logout({ redirectUri: window.location.origin }),
    []
  );

  const isSuperAdmin = useMemo(
    () => (tokenParsed?.realm_access?.roles || []).includes("super-admin"),
    [tokenParsed]
  );

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

  return (
    <AuthContext.Provider value={{ isLoading, isAuthenticated, isSuperAdmin, user, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
};
