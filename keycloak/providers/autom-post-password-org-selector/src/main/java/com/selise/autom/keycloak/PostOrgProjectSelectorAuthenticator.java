package com.selise.autom.keycloak;

import jakarta.ws.rs.core.Response;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.Authenticator;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.GroupModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.OrganizationModel;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.organization.OrganizationProvider;

/**
 * After org selection, presents a project picker scoped to the user's KC group
 * memberships within the selected organisation's group hierarchy.
 *
 * Project groups live at /{orgName}/{projectName} in the KC group tree.
 * Users gain access by being members of the project group itself or any of its
 * subgroups (e.g. /{orgName}/{projectName}/admins).
 *
 * If the user has no project memberships the picker remains visible with an
 * explicit access message. Silently issuing an unscoped token is unsafe and
 * makes a missing Keycloak project hierarchy look like a broken UI redirect.
 * The project chooser is always shown for an interactive login, even when only
 * one project is accessible. This makes the workspace boundary explicit and
 * guarantees the user sees the required organization → project sequence.
 *
 * Silent project switching:
 *   Pass kc_project_hint=<projectName> in the auth request. When the request
 *   also carries prompt=none (silent re-auth), this authenticator resolves the
 *   hint to a KC group and auto-selects it, updating the project_id user session
 *   note so the issued token reflects the new project without any UI interaction.
 *   If prompt=none and no valid hint is present the existing session note is kept.
 */
public final class PostOrgProjectSelectorAuthenticator implements Authenticator {
    static final String ID = "autom-post-org-project-selector";

    /** User session note key for the selected KC project group ID (MongoDB ItemId). */
    static final String PROJECT_ID_NOTE = "autom.project.group.id";
    /** User session note key for the selected project display name. */
    static final String PROJECT_NAME_NOTE = "autom.project.name";

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        UserModel user = context.getUser();
        if (user == null) {
            context.failure(AuthenticationFlowError.GENERIC_AUTHENTICATION_ERROR);
            return;
        }

        OrganizationModel org = resolveOrg(context);
        if (org == null) {
            // Super-admin or org-less path — no project selection needed.
            context.success();
            return;
        }

        List<GroupModel> projects = accessibleProjects(context, user, org);
        if (projects.isEmpty()) {
            showPicker(context, org, projects, null);
            return;
        }

        // Check for a project hint sent in the auth request (silent project switch).
        // kc_project_hint accepts either the KC group name or its UUID.
        String hint = context.getAuthenticationSession().getClientNote("kc_project_hint");
        if (hint != null && !hint.isBlank()) {
            GroupModel hinted = projects.stream()
                    .filter(g -> g.getName().equalsIgnoreCase(hint) || g.getId().equals(hint))
                    .findFirst()
                    .orElse(null);
            if (hinted != null) {
                selectProject(context, hinted);
                context.success();
                return;
            }
        }

        // prompt=none: no UI interaction allowed. Keep the existing project selection
        // from the user session note (set during a previous interactive auth flow);
        // the protocol mapper will emit that stored value unchanged.
        String prompt = context.getAuthenticationSession().getClientNote("prompt");
        if ("none".equals(prompt)) {
            context.success();
            return;
        }

        showPicker(context, org, projects, null);
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        UserModel user = context.getUser();
        if (user == null) {
            context.failure(AuthenticationFlowError.GENERIC_AUTHENTICATION_ERROR);
            return;
        }

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

        selectProject(context, selected);
        context.success();
    }

    private OrganizationModel resolveOrg(AuthenticationFlowContext context) {
        String orgId = context.getAuthenticationSession()
                .getAuthNote(OrganizationModel.ORGANIZATION_ATTRIBUTE);
        if (orgId == null) return null;
        return context.getSession().getProvider(OrganizationProvider.class).getById(orgId);
    }

    private List<GroupModel> accessibleProjects(
            AuthenticationFlowContext context, UserModel user, OrganizationModel org) {

        // Find the org's top-level KC group by matching name or alias.
        GroupModel orgGroup = context.getRealm().getTopLevelGroupsStream()
                .filter(g -> matchesOrg(g, org))
                .findFirst()
                .orElse(null);

        if (orgGroup == null) return List.of();

        Set<String> userGroupIds = user.getGroupsStream()
                .map(GroupModel::getId)
                .collect(Collectors.toSet());

        // Organization owners/admins have every project. In the group layout,
        // org-wide authority is assigned through /{org}/admins (and optionally
        // /{org}/owners), not by making users direct members of /{org}.
        boolean orgLevelMember = userGroupIds.contains(orgGroup.getId())
                || orgGroup.getSubGroupsStream(0, 50)
                        .filter(g -> g.getName().equalsIgnoreCase("admins")
                                  || g.getName().equalsIgnoreCase("owners"))
                        .anyMatch(g -> userGroupIds.contains(g.getId()));

        // Direct subgroups of the org group are projects; 'admins' is a role subgroup, not a project.
        return orgGroup.getSubGroupsStream(0, 500)
                .filter(g -> !g.getName().equalsIgnoreCase("admins")
                          && !g.getName().equalsIgnoreCase("owners"))
                .filter(g -> orgLevelMember || userIsMemberOfProject(g, userGroupIds))
                .sorted(Comparator.comparing(GroupModel::getName, String.CASE_INSENSITIVE_ORDER))
                .collect(Collectors.toList());
    }

    private boolean userIsMemberOfProject(GroupModel projectGroup, Set<String> userGroupIds) {
        if (userGroupIds.contains(projectGroup.getId())) return true;
        // Check indirect membership via subgroups (e.g. /org/project/admins).
        return projectGroup.getSubGroupsStream(0, 50)
                .anyMatch(sub -> userGroupIds.contains(sub.getId()));
    }

    private boolean matchesOrg(GroupModel group, OrganizationModel org) {
        String groupName = normalize(group.getName());
        return groupName.equals(normalize(org.getName())) || groupName.equals(normalize(org.getAlias()));
    }

    /** Keeps legacy group names such as Test_3 compatible with alias test-3. */
    private static String normalize(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase(java.util.Locale.ROOT);
    }

    private void selectProject(AuthenticationFlowContext context, GroupModel project) {
        // Auth note: available within this request's authentication flow.
        context.getAuthenticationSession().setAuthNote(PROJECT_ID_NOTE, project.getId());
        // Client note: persisted in the client session after auth completes.
        context.getAuthenticationSession().setClientNote(PROJECT_ID_NOTE, project.getId());
        // User session notes: propagated to UserSessionModel by AuthenticationManager.
        // Use KC's built-in "User Session Note" protocol mapper to surface these in the token.
        context.getAuthenticationSession().setUserSessionNote(PROJECT_ID_NOTE, project.getId());
        context.getAuthenticationSession().setUserSessionNote(PROJECT_NAME_NOTE, project.getName());
    }

    private void showPicker(
            AuthenticationFlowContext context, OrganizationModel org,
            List<GroupModel> projects, String errorKey) {
        LoginFormsProvider form = context.form()
                .setAttribute("orgName", org.getName())
                .setAttribute("projects", projects);
        if (errorKey != null) form.setError(errorKey);
        context.challenge(form.createForm("post-org-project-picker.ftl"));
    }

    @Override public boolean requiresUser() { return true; }
    @Override public boolean configuredFor(KeycloakSession session, RealmModel realm, UserModel user) { return true; }
    @Override public void setRequiredActions(KeycloakSession session, RealmModel realm, UserModel user) { }
    @Override public void close() { }
}
