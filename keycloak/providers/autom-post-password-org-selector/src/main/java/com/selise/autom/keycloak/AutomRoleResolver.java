package com.selise.autom.keycloak;

import java.util.Set;
import org.keycloak.models.GroupModel;

/**
 * Computes the caller's structural role for the currently active org/project,
 * from Keycloak group membership alone — shared by
 * {@link PostOrgProjectSelectorAuthenticator} (sets it at login) and
 * {@link AutomProjectSwitchResource} (keeps it current after a switch), so the
 * same rule applies whether the token came from an interactive login or a
 * mid-session switch.
 *
 * Mirrors the group layout the business backend's own provisioning code
 * builds (Autom.Application.SuperAdmin.Orgs.*CommandHandler): org-wide
 * access via /{org}/admins (and legacy /{org}/owners), project-admin via
 * /{org}/{project}/admins, project-member via plain /{org}/{project}
 * membership.
 *
 * Cannot distinguish "owner" from "org-admin" — both are represented by the
 * same /{org}/admins group in Keycloak; that distinction only exists in the
 * business backend's own OrgMember.OrgRole field. "org-admin" is emitted for
 * both, matching how Autom.Application.Me.GetMyPermissions.
 * GetMyPermissionsQueryHandler already treats owner and org-admin
 * identically (full access).
 */
final class AutomRoleResolver {

    /** User session note key for the resolved role; mapped to the "active_role" token claim. */
    static final String ACTIVE_ROLE_NOTE = "autom.active.role";

    static final String ORG_ADMIN = "org-admin";
    static final String PROJECT_ADMIN = "project-admin";
    static final String PROJECT_MEMBER = "project-member";

    /**
     * @param orgGroup     the active organization's top-level KC group.
     * @param projectGroup the active project's KC group, or null when no
     *                     project is selected (org-wide roles do not need one).
     * @param userGroupIds every KC group id the user is a direct member of.
     * @return the resolved role name, or null when the user has neither
     *         org-wide nor project-scoped access (should not normally happen —
     *         both call sites already gate on access before calling this).
     */
    static String resolve(GroupModel orgGroup, GroupModel projectGroup, Set<String> userGroupIds) {
        boolean orgWide = userGroupIds.contains(orgGroup.getId())
                || orgGroup.getSubGroupsStream(0, 50)
                        .filter(g -> g.getName().equalsIgnoreCase("admins")
                                  || g.getName().equalsIgnoreCase("owners"))
                        .anyMatch(g -> userGroupIds.contains(g.getId()));
        if (orgWide) return ORG_ADMIN;

        if (projectGroup == null) return null;

        boolean projectAdmin = projectGroup.getSubGroupsStream(0, 50)
                .filter(g -> g.getName().equalsIgnoreCase("admins"))
                .anyMatch(g -> userGroupIds.contains(g.getId()));
        if (projectAdmin) return PROJECT_ADMIN;

        if (userGroupIds.contains(projectGroup.getId())) return PROJECT_MEMBER;

        return null;
    }

    private AutomRoleResolver() { }
}
