package com.selise.autom.keycloak;

import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.authenticators.conditional.ConditionalAuthenticator;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;

/**
 * Condition that always evaluates to true, making the enclosing CONDITIONAL
 * subflow run unconditionally after the credential-authentication alternatives
 * (Cookie / Username-Password) complete at the same flow level.
 *
 * This is the standard KC pattern for post-authentication steps (analogous to
 * how MFA CONDITIONAL subflows work in KC's built-in browser flow).
 */
public final class AutomAlwaysTrueCondition implements ConditionalAuthenticator {
    static final String ID = "autom-condition-always";

    @Override
    public boolean matchCondition(AuthenticationFlowContext context) {
        return true;
    }

    @Override public void authenticate(AuthenticationFlowContext context) { context.success(); }
    @Override public void action(AuthenticationFlowContext context) { }
    @Override public boolean requiresUser() { return false; }
    @Override public boolean configuredFor(KeycloakSession s, RealmModel r, UserModel u) { return true; }
    @Override public void setRequiredActions(KeycloakSession s, RealmModel r, UserModel u) { }
    @Override public void close() { }
}
