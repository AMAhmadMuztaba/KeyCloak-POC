# KeyCLOAK — Multi-Org Project Login

## Post-password organization selector

`keycloak/providers/autom-post-password-org-selector` is a Keycloak
Authenticator SPI compiled into the local Keycloak image. It changes the
business login to:

```
Keycloak email + password → Keycloak organization cards → org-scoped token → project selection
```

The cards are rendered by the Keycloak `autom` login theme, never by React. The
provider verifies the authenticated user's native Keycloak membership and stores
only the selected organization UUID in the server-side authentication session.
One organization is selected automatically; no membership ends in a Keycloak
access-denied screen.

Use `docker compose up --build` to build and run the local image. For an
existing Keycloak server, deploy the generated JAR from
`keycloak/providers/autom-post-password-org-selector/target/` to
`/opt/keycloak/providers/`, run `kc.sh build --features=organization`, restart
Keycloak, then run `Initial script/autom-realm-init.py`. The initializer will not switch the
browser flow unless Keycloak recognizes the provider.

A full-stack demo of Keycloak-powered authentication with multi-org / multi-project workspace selection and an admin bypass flow.

## Flow

```
Landing → [Keycloak Login] → Org Select → Project Select → Dashboard
                                                ↓ (admin only)
                                          [Skip button] → Admin Dashboard
```

---

## Quick start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Compose v2)
- [Node.js 20+](https://nodejs.org/) (for local frontend dev)

### 1 — Start Keycloak + backend

```bash
# Copy env file (optional, defaults are fine for local dev)
cp .env.example .env

# Start everything
docker compose up -d

# Watch the init container configure demo users (~30 s after KC starts)
docker compose logs -f keycloak-init
```

Keycloak admin console → http://localhost:8080  
Login: use `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` from your `.env`

### 2 — Start the frontend (dev mode)

```bash
cd frontend
npm install
npm run dev
```

Open → http://localhost:3000

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser (React + Vite, port 3000)              │
│  keycloak-js  →  OIDC Authorization Code + PKCE │
└────────────────────┬────────────────────────────┘
                     │ JWT Bearer
         ┌───────────▼───────────┐
         │  Express backend       │  port 4000
         │  express-jwt + jwks-rsa│
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │  Keycloak 24          │  port 8080
         │  realm: app-realm     │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │  PostgreSQL 15        │  (internal)
         └───────────────────────┘
```

## Group / Org / Project model

Organisations and projects are Keycloak **Groups**:

```
/org-alpha
  /project-1
  /project-2
/org-beta
  /project-3
/org-gamma
  /project-4
  /project-5
```

The `app-client` has a **groups protocol mapper** that injects these paths  
into the JWT as `groups: ["/org-alpha", "/org-alpha/project-1", …]`.

The frontend parses this to drive the selection UI with no extra API call.

## Roles

| Role    | Effect |
|---------|--------|
| `admin` | JWT `realm_access.roles` includes `"admin"` → shows Skip button |
| `user`  | Regular project access only |

## Backend API (protected)

All routes require a valid `Authorization: Bearer <token>` header.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Public health check |
| GET | `/api/me` | Current user + orgs + projects |
| GET | `/api/orgs` | User's organisations |
| GET | `/api/orgs/:org/projects` | Projects in a specific org |

## Development

```bash
# Rebuild Keycloak realm from scratch
docker compose down -v && docker compose up -d

# Backend only (local, needs KC running in Docker)
cd backend && npm install && npm run dev

# Frontend only
cd frontend && npm install && npm run dev
```

## Adding a new org or project

1. Go to Keycloak admin → realm `app-realm` → Groups
2. Create a top-level group (org) or a subgroup (project)
3. Assign users to the group
4. The app picks it up immediately from the JWT (no redeploy needed)
# KeyCloak-POC
