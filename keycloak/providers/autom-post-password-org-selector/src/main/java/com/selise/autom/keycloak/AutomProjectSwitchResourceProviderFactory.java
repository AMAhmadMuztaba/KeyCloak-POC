package com.selise.autom.keycloak;

import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.services.resource.RealmResourceProvider;
import org.keycloak.services.resource.RealmResourceProviderFactory;

public final class AutomProjectSwitchResourceProviderFactory implements RealmResourceProviderFactory {
    /** The URL segment: /realms/{realm}/autom/... */
    public static final String ID = "autom";

    @Override public String getId() { return ID; }

    @Override
    public RealmResourceProvider create(KeycloakSession session) {
        return new AutomProjectSwitchResourceProvider(session);
    }

    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
