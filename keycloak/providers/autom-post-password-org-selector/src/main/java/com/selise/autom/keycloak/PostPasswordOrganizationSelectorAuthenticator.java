package com.selise.autom.keycloak;

import jakarta.ws.rs.core.Response;
import java.util.Comparator;
import java.util.List;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.Authenticator;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.OrganizationModel;
import org.keycloak.models.RealmModel;
import org.keycloak.models.RoleModel;
import org.keycloak.models.UserModel;
import org.keycloak.organization.OrganizationProvider;

/**
 * Selects one native Keycloak Organization only after Username Password Form
 * has authenticated the user. The built-in organization authenticator cannot
 * be used here because it is intentionally identity-first.
 *
 * Silent re-auth (prompt=none):
 *   Reads the organization alias from the OIDC scope string
 *   (format: "organization:<alias>"). If it matches a membership, that org is
 *   selected silently so the project selector step can run next. With no
 *   matching hint and prompt=none the step succeeds without updating the
 *   session note, preserving the org from the prior interactive login.
 */
public final class PostPasswordOrganizationSelectorAuthenticator implements Authenticator {
    static final String ID = "autom-post-password-org-selector";
    /** Stable token claim source; unlike KC's native organization scope this is refresh-safe. */
    static final String ACTIVE_ORGANIZATION_ID_NOTE = "autom.organization.id";
    /**
     * The org's alias (e.g. "test-3"), refresh-safe like {@link #ACTIVE_ORGANIZATION_ID_NOTE}.
     * KC's native {@code organization} claim carries the alias too, but only the one
     * requested at original login — it does not follow an in-session org switch
     * (Keycloak refresh tokens can't silently re-scope to a different org). This note
     * is updated by {@link AutomProjectSwitchResource} on every switch, giving the
     * frontend a reliable alias source for building the next login/silent-check's
     * {@code organization:<alias>} scope hint (see requestedOidcScope() in main.tsx).
     */
    static final String ACTIVE_ORGANIZATION_ALIAS_NOTE = "autom.organization.alias";

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        UserModel user = context.getUser();
        if (user == null) {
            context.failure(AuthenticationFlowError.GENERIC_AUTHENTICATION_ERROR);
            return;
        }

        // Super-admins are never org members — skip org selection entirely.
        RoleModel superAdminRole = context.getRealm().getRole("super-admin");
        if (superAdminRole != null && user.hasRole(superAdminRole)) {
            context.success();
            return;
        }

        List<OrganizationModel> organizations = organizationsFor(context, user);
        if (organizations.isEmpty()) {
            LoginFormsProvider form = context.form();
            form.setError("automNoOrganizationAccess");
            context.failure(AuthenticationFlowError.GENERIC_AUTHENTICATION_ERROR,
                    form.createErrorPage(Response.Status.FORBIDDEN),
                    "User has no enabled Keycloak organization membership", "automNoOrganizationAccess");
            return;
        }

        if (organizations.size() == 1) {
            select(context, organizations.getFirst());
            context.success();
            return;
        }

        // Try to select the org from the auth request's scope (organization:<alias>).
        // This covers both silent project switches and any re-auth that carries the
        // current org in scope so this step can complete without UI.
        String scope = context.getAuthenticationSession().getClientNote("scope");
        String alias = extractOrgAliasFromScope(scope);
        if (alias != null) {
            String finalAlias = alias;
            OrganizationModel hinted = organizations.stream()
                    .filter(o -> o.getAlias().equalsIgnoreCase(finalAlias)
                              || o.getName().equalsIgnoreCase(finalAlias))
                    .findFirst()
                    .orElse(null);
            if (hinted != null) {
                select(context, hinted);
                context.success();
                return;
            }
        }

        // prompt=none: no UI interaction allowed. Keep existing org from user session;
        // the token's organization claim is set by KC's native org scope handling anyway.
        String prompt = context.getAuthenticationSession().getClientNote("prompt");
        if ("none".equals(prompt)) {
            context.success();
            return;
        }

        showPicker(context, organizations, null);
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        UserModel user = context.getUser();
        if (user == null) {
            context.failure(AuthenticationFlowError.GENERIC_AUTHENTICATION_ERROR);
            return;
        }

        List<OrganizationModel> organizations = organizationsFor(context, user);
        String alias = context.getHttpRequest().getDecodedFormParameters().getFirst("organization");
        OrganizationModel selected = organizations.stream()
                .filter(organization -> organization.getAlias().equals(alias))
                .findFirst()
                .orElse(null);

        if (selected == null) {
            showPicker(context, organizations, "automOrganizationSelectionRequired");
            return;
        }

        select(context, selected);
        context.success();
    }

    private List<OrganizationModel> organizationsFor(AuthenticationFlowContext context, UserModel user) {
        OrganizationProvider provider = context.getSession().getProvider(OrganizationProvider.class);
        return provider.getByMember(user)
                .filter(OrganizationModel::isEnabled)
                .sorted(Comparator.comparing(OrganizationModel::getName, String.CASE_INSENSITIVE_ORDER))
                .toList();
    }

    private void select(AuthenticationFlowContext context, OrganizationModel organization) {
        // Auth note: read by OrganizationMembership protocol mapper when building the token.
        context.getAuthenticationSession().setAuthNote(OrganizationModel.ORGANIZATION_ATTRIBUTE, organization.getId());
        // Client note: persisted in the client session after authentication completes.
        context.getAuthenticationSession().setClientNote(OrganizationModel.ORGANIZATION_ATTRIBUTE, organization.getId());
        // User session note: AuthenticationManager propagates these to UserSessionModel on session
        // creation. KC 26's CookieAuthenticator reads this note when validating org-scoped SSO
        // sessions — without it the cookie check falls through to the org picker on every refresh.
        context.getAuthenticationSession().setUserSessionNote(OrganizationModel.ORGANIZATION_ATTRIBUTE, organization.getId());
        context.getAuthenticationSession().setUserSessionNote(ACTIVE_ORGANIZATION_ID_NOTE, organization.getId());
        context.getAuthenticationSession().setUserSessionNote(ACTIVE_ORGANIZATION_ALIAS_NOTE, organization.getAlias());
        // Request-scoped context: used within this authentication request only.
        context.getSession().getContext().setOrganization(organization);
    }

    private void showPicker(AuthenticationFlowContext context, List<OrganizationModel> organizations, String errorKey) {
        LoginFormsProvider form = context.form().setAttribute("organizations", organizations);
        if (errorKey != null) {
            form.setError(errorKey);
        }
        context.challenge(form.createForm("post-password-organization-picker.ftl"));
    }

    /**
     * Extracts the organization alias from an OIDC scope string.
     * The format used by the React app is "openid profile email organization:<alias>".
     */
    private static String extractOrgAliasFromScope(String scope) {
        if (scope == null) return null;
        for (String part : scope.split("\\s+")) {
            if (part.startsWith("organization:")) {
                String extracted = part.substring("organization:".length());
                return extracted.isBlank() ? null : extracted;
            }
        }
        return null;
    }

    @Override public boolean requiresUser() { return true; }
    @Override public boolean configuredFor(KeycloakSession session, RealmModel realm, UserModel user) { return true; }
    @Override public void setRequiredActions(KeycloakSession session, RealmModel realm, UserModel user) { }
    @Override public void close() { }
}
