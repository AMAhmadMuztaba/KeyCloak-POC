package com.selise.autom.keycloak;

import java.util.List;
import org.keycloak.models.OrganizationModel;

/**
 * Shared "is MFA mandatory for this org" check, read from the native org's
 * mfaMandatory attribute (set by KeycloakAdminClient.SetKcOrganizationMfaMandatoryAsync).
 * Used both at login time (AutomMfaEnforcementAuthenticator) and on an
 * in-session org switch (AutomProjectSwitchResource) so the two enforcement
 * points can never drift on how the attribute is parsed.
 */
final class AutomMfaUtil {
    private AutomMfaUtil() { }

    static boolean isMfaMandatory(OrganizationModel org) {
        List<String> values = org.getAttributes().get("mfaMandatory");
        return values != null && !values.isEmpty() && "true".equalsIgnoreCase(values.get(0));
    }
}
