package com.selise.autom.keycloak;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;
import org.keycloak.Config;
import org.keycloak.authentication.InitiatedActionSupport;
import org.keycloak.authentication.RequiredActionContext;
import org.keycloak.authentication.RequiredActionFactory;
import org.keycloak.authentication.RequiredActionProvider;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.GroupModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.models.OrganizationModel;
import org.keycloak.models.UserModel;
import org.keycloak.organization.OrganizationProvider;

/**
 * Project selection as a REQUIRED ACTION, not a flow authenticator -- exists
 * purely so it can be sequenced AFTER CONFIGURE_TOTP/autom-optional-totp via
 * required-action priority (registered at 59, one above their 58).
 *
 * Required actions all run in ONE phase after the entire authentication flow
 * (every one of its challenges, including PostOrgProjectSelectorAuthenticator's
 * own in-flow picker) finishes -- confirmed live: reordering flow EXECUTIONS
 * does not change when a queued required action's page appears relative to a
 * flow challenge, since the flow's challenges and the required-action phase
 * are two entirely separate stages, not interleaved. The only way to get a
 * real "org -> MFA -> project" order is to make project selection ALSO a
 * required action, so its position can be controlled the same way
 * autom-onboarding-profile/VERIFY_EMAIL/UPDATE_PASSWORD/CONFIGURE_TOTP
 * already are.
 *
 * PostOrgProjectSelectorAuthenticator queues THIS (instead of showing its own
 * in-flow picker) only for the one case that needs the reordering: the org
 * has MFA mandatory and the user hasn't configured it yet. Every other login
 * is completely unaffected -- the in-flow picker still runs exactly as
 * before, and this required action is never queued at all.
 *
 * Reuses PostOrgProjectSelectorAuthenticator's own group-membership logic
 * (accessibleProjects/matchesOrg/normalize) by duplicating it here rather
 * than extracting a shared utility for this one extra caller -- same
 * decision already made elsewhere in this codebase (see that class's own
 * comments on AutomRoleResolver being the one piece that WAS worth sharing).
 */
public class AutomProjectSelectionRequiredAction implements RequiredActionProvider, RequiredActionFactory {
    static final String ID = "autom-project-selection";

    @Override
    public InitiatedActionSupport initiatedActionSupport() {
        return InitiatedActionSupport.NOT_SUPPORTED;
    }

    @Override
    public void evaluateTriggers(RequiredActionContext context) { }

    @Override
    public void requiredActionChallenge(RequiredActionContext context) {
        UserModel user = context.getUser();
        OrganizationModel org = resolveOrg(context);
        if (org == null) {
            context.success();
            return;
        }

        List<GroupModel> projects = accessibleProjects(context, user, org);
        if (projects.size() == 1) {
            selectProject(context, org, projects.getFirst());
            context.success();
            return;
        }

        showPicker(context, org, projects, null);
    }

    @Override
    public void processAction(RequiredActionContext context) {
        UserModel user = context.getUser();
        OrganizationModel org = resolveOrg(context);
        if (org == null) {
            context.success();
            return;
        }

        List<GroupModel> projects = accessibleProjects(context, user, org);
        String submittedId = context.getHttpRequest().getDecodedFormParameters().getFirst("project");
        GroupModel selected = projects.stream()
                .filter(g -> g.getId().equals(submittedId))
                .findFirst()
                .orElse(null);

        if (selected == null) {
            showPicker(context, org, projects, "automProjectSelectionRequired");
            return;
        }

        selectProject(context, org, selected);
        context.success();
    }

    private OrganizationModel resolveOrg(RequiredActionContext context) {
        String orgId = context.getAuthenticationSession()
                .getAuthNote(OrganizationModel.ORGANIZATION_ATTRIBUTE);
        if (orgId == null) return null;
        return context.getSession().getProvider(OrganizationProvider.class).getById(orgId);
    }

    private List<GroupModel> accessibleProjects(
            RequiredActionContext context, UserModel user, OrganizationModel org) {

        GroupModel orgGroup = context.getRealm().getTopLevelGroupsStream()
                .filter(g -> matchesOrg(g, org))
                .findFirst()
                .orElse(null);

        if (orgGroup == null) return List.of();

        Set<String> userGroupIds = user.getGroupsStream()
                .map(GroupModel::getId)
                .collect(Collectors.toSet());

        boolean orgLevelMember = userGroupIds.contains(orgGroup.getId())
                || orgGroup.getSubGroupsStream(0, 50)
                        .filter(g -> g.getName().equalsIgnoreCase("admins")
                                  || g.getName().equalsIgnoreCase("owners"))
                        .anyMatch(g -> userGroupIds.contains(g.getId()));

        return orgGroup.getSubGroupsStream(0, 500)
                .filter(g -> !g.getName().equalsIgnoreCase("admins")
                          && !g.getName().equalsIgnoreCase("owners"))
                .filter(g -> orgLevelMember || userIsMemberOfProject(g, userGroupIds))
                .sorted(Comparator.comparing(GroupModel::getName, String.CASE_INSENSITIVE_ORDER))
                .collect(Collectors.toList());
    }

    private boolean userIsMemberOfProject(GroupModel projectGroup, Set<String> userGroupIds) {
        if (userGroupIds.contains(projectGroup.getId())) return true;
        return projectGroup.getSubGroupsStream(0, 50)
                .anyMatch(sub -> userGroupIds.contains(sub.getId()));
    }

    private boolean matchesOrg(GroupModel group, OrganizationModel org) {
        String groupName = normalize(group.getName());
        return groupName.equals(normalize(org.getName())) || groupName.equals(normalize(org.getAlias()));
    }

    private static String normalize(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase(Locale.ROOT);
    }

    private void selectProject(RequiredActionContext context, OrganizationModel org, GroupModel project) {
        context.getAuthenticationSession().setAuthNote(
                PostOrgProjectSelectorAuthenticator.PROJECT_ID_NOTE, project.getId());
        context.getAuthenticationSession().setClientNote(
                PostOrgProjectSelectorAuthenticator.PROJECT_ID_NOTE, project.getId());
        context.getAuthenticationSession().setUserSessionNote(
                PostOrgProjectSelectorAuthenticator.PROJECT_ID_NOTE, project.getId());
        context.getAuthenticationSession().setUserSessionNote(
                PostOrgProjectSelectorAuthenticator.PROJECT_NAME_NOTE, project.getName());

        GroupModel orgGroup = context.getRealm().getTopLevelGroupsStream()
                .filter(g -> matchesOrg(g, org))
                .findFirst()
                .orElse(null);
        if (orgGroup != null) {
            Set<String> userGroupIds = context.getUser().getGroupsStream()
                    .map(GroupModel::getId)
                    .collect(Collectors.toSet());
            String role = AutomRoleResolver.resolve(orgGroup, project, userGroupIds);
            if (role != null) {
                context.getAuthenticationSession().setUserSessionNote(AutomRoleResolver.ACTIVE_ROLE_NOTE, role);
            }
        }
    }

    private void showPicker(
            RequiredActionContext context, OrganizationModel org,
            List<GroupModel> projects, String errorKey) {
        LoginFormsProvider form = context.form()
                .setAttribute("orgName", org.getName())
                .setAttribute("projects", projects);
        if (errorKey != null) form.setError(errorKey);
        context.challenge(form.createForm("post-org-project-picker.ftl"));
    }

    @Override public String getId() { return ID; }
    @Override public String getDisplayText() { return "Select project (Autom, post-org, post-MFA)"; }
    @Override public boolean isOneTimeAction() { return true; }
    @Override public RequiredActionProvider create(KeycloakSession session) { return this; }
    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
