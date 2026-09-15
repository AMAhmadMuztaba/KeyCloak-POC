package com.selise.autom.keycloak;

import java.util.List;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.Authenticator;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.OrganizationModel;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.credential.OTPCredentialModel;
import org.keycloak.organization.OrganizationProvider;

/**
 * Runs after {@link PostOrgProjectSelectorAuthenticator} in the custom browser
 * flow (same level, next in order). For an already-active member logging in
 * normally — the invite-time required-action queueing in KeycloakAdminClient
 * only covers brand-new invites — this is the only enforcement point: reads
 * the active org's native "mfaMandatory" attribute (set by
 * KeycloakAdminClient.SetKcOrganizationMfaMandatoryAsync, no callback into the
 * .NET API needed here) and, if true and the user has no TOTP credential yet,
 * queues the stock CONFIGURE_TOTP required action on THIS authentication
 * session — required actions are processed after the whole browser flow
 * completes (confirmed earlier this session), so the user lands on the MFA
 * page right after picking their org/project, with no Skip button (stock
 * UpdateTotp never honors cancel-aia on a queued action — see
 * AutomOptionalTotp.java for why that's exactly the desired "no skip"
 * behavior here, achieved with zero extra provider code).
 *
 * Session-scoped, not user-scoped: uses AuthenticationSessionModel.addRequiredAction,
 * not UserModel.addRequiredAction, so it re-evaluates fresh on every login
 * rather than permanently marking the user — correct, since mfaMandatory can be
 * turned off later and a stale permanent required action would then never clear.
 */
public final class AutomMfaEnforcementAuthenticator implements Authenticator {
    static final String ID = "autom-mfa-enforcement";

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        UserModel user = context.getUser();
        if (user == null) {
            context.success();
            return;
        }

        OrganizationModel org = resolveOrg(context);
        if (org == null) {
            context.success();
            return;
        }

        if (isMfaMandatory(org) && !user.credentialManager().isConfiguredFor(OTPCredentialModel.TYPE)) {
            context.getAuthenticationSession().addRequiredAction(UserModel.RequiredAction.CONFIGURE_TOTP);
        }

        context.success();
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        context.success();
    }

    private static boolean isMfaMandatory(OrganizationModel org) {
        List<String> values = org.getAttributes().get("mfaMandatory");
        return values != null && !values.isEmpty() && "true".equalsIgnoreCase(values.get(0));
    }

    private OrganizationModel resolveOrg(AuthenticationFlowContext context) {
        String orgId = context.getAuthenticationSession()
                .getAuthNote(OrganizationModel.ORGANIZATION_ATTRIBUTE);
        if (orgId == null) return null;
        return context.getSession().getProvider(OrganizationProvider.class).getById(orgId);
    }

    @Override public boolean requiresUser() { return true; }
    @Override public boolean configuredFor(KeycloakSession session, RealmModel realm, UserModel user) { return true; }
    @Override public void setRequiredActions(KeycloakSession session, RealmModel realm, UserModel user) { }
    @Override public void close() { }
}
