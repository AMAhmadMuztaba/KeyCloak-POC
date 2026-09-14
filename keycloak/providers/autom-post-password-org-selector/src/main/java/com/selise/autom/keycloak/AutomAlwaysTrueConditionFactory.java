package com.selise.autom.keycloak;

import java.util.List;
import org.keycloak.Config;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.AuthenticatorFactory;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;

public final class AutomAlwaysTrueConditionFactory implements AuthenticatorFactory {
    private static final AuthenticationExecutionModel.Requirement[] REQUIREMENTS = {
            AuthenticationExecutionModel.Requirement.REQUIRED,
            AuthenticationExecutionModel.Requirement.DISABLED,
    };

    @Override public String getId() { return AutomAlwaysTrueCondition.ID; }
    @Override public String getDisplayType() { return "Autom – Condition (always true)"; }
    @Override public String getReferenceCategory() { return "condition"; }
    @Override public boolean isConfigurable() { return false; }
    @Override public boolean isUserSetupAllowed() { return false; }
    @Override public AuthenticationExecutionModel.Requirement[] getRequirementChoices() { return REQUIREMENTS; }
    @Override public String getHelpText() { return "Always evaluates to true; makes the enclosing CONDITIONAL subflow run unconditionally after authentication."; }
    @Override public List<ProviderConfigProperty> getConfigProperties() { return List.of(); }
    @Override public Authenticator create(KeycloakSession session) { return new AutomAlwaysTrueCondition(); }
    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
