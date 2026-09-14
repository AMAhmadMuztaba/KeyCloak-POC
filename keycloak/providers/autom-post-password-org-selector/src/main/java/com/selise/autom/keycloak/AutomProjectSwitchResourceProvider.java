package com.selise.autom.keycloak;

import org.keycloak.models.KeycloakSession;
import org.keycloak.services.resource.RealmResourceProvider;

public final class AutomProjectSwitchResourceProvider implements RealmResourceProvider {
    private final KeycloakSession session;

    public AutomProjectSwitchResourceProvider(KeycloakSession session) {
        this.session = session;
    }

    @Override
    public Object getResource() {
        return new AutomProjectSwitchResource(session);
    }

    @Override
    public void close() { }
}
