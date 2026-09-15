package com.selise.autom.keycloak;

import jakarta.ws.rs.core.MultivaluedMap;
import org.keycloak.authentication.RequiredActionContext;
import org.keycloak.authentication.RequiredActionFactory;
import org.keycloak.authentication.RequiredActionProvider;
import org.keycloak.authentication.requiredactions.UpdateTotp;
import org.keycloak.models.KeycloakSession;

/**
 * Stock UpdateTotp.processAction() never checks for "cancel-aia" itself -- that gate lives in
 * LoginActionsService.isCancelAppInitiatedAction(), which only short-circuits when the action was
 * triggered via kc_action (app-initiated). For a plain queued required action (added via
 * user.requiredActions, as our invite flow does), that gate is false, so the form still submits
 * into UpdateTotp.processAction() as usual and stock behavior demands a valid TOTP code -- proven
 * live ("Please specify authenticator code."). This subclass intercepts cancel-aia itself, before
 * delegating to the stock validation, so Skip works regardless of how the action was triggered.
 *
 * login-config-totp.ftl is ALSO used to render stock CONFIGURE_TOTP directly (queued instead of
 * this provider for orgs with MFA mandatory -- see KeycloakAdminClient.BuildInviteRequiredActions
 * and AutomMfaEnforcementAuthenticator), where Skip must NEVER show since stock UpdateTotp never
 * honors cancel-aia on a queued action. requiredActionChallenge() sets automSkippable=true before
 * delegating to the stock renderer (same "set attribute, then call super" trick as
 * AutomOnboardingProfile's joining-context injection) so the template can tell the two apart --
 * stock CONFIGURE_TOTP never sets it, so it defaults to not-shown.
 */
public class AutomOptionalTotp extends UpdateTotp {

    public static final String PROVIDER_ID = "autom-optional-totp";

    @Override
    public void requiredActionChallenge(RequiredActionContext context) {
        context.form().setAttribute("automSkippable", true);
        super.requiredActionChallenge(context);
    }

    @Override
    public void processAction(RequiredActionContext context) {
        MultivaluedMap<String, String> formData = context.getHttpRequest().getDecodedFormParameters();
        if (formData.containsKey("cancel-aia")) {
            context.success();
            return;
        }
        super.processAction(context);
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getDisplayText() {
        return "Configure OTP (optional, Autom)";
    }

    @Override
    public RequiredActionProvider create(KeycloakSession session) {
        return this;
    }
}
