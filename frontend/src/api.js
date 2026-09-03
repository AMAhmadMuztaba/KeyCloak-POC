import keycloak from "./keycloak";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:4000";

export async function apiFetch(path, method = "GET", body) {
  // Always refresh token if it expires within 30 s (M3)
  await keycloak.updateToken(30).catch(() => {
    keycloak.login(); // session expired — redirect to login
  });
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${keycloak.token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
