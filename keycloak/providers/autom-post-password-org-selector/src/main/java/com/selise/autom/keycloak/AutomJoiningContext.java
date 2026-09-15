package com.selise.autom.keycloak;

import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;
import org.keycloak.models.GroupModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.OrganizationModel;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.organization.OrganizationProvider;

/**
 * Resolves "which org/role is this user joining" purely from the user's own
 * Keycloak membership (native Organization membership + group membership) —
 * unlike {@link PostOrgProjectSelectorAuthenticator}, which resolves the
 * ACTIVE org from a session note set by the picker flow, this has no such
 * note to read from: the invite action-token entry point never runs the
 * org/project picker (a different entry point entirely), so at onboarding
 * time the org is whatever the .NET backend already added the user to as
 * part of the invite (POST .../organizations/{orgId}/members), not a
 * user-selected one.
 *
 * Used only for the read-only "Joining {org} · {role}" display on the
 * onboarding details page — matches the design, which shows org name + role
 * label only, no project name.
 */
final class AutomJoiningContext {

    final String orgName;
    final String roleLabel;

    private AutomJoiningContext(String orgName, String roleLabel) {
        this.orgName = orgName;
        this.roleLabel = roleLabel;
    }

    static AutomJoiningContext resolve(KeycloakSession session, RealmModel realm, UserModel user) {
        OrganizationProvider orgProvider = session.getProvider(OrganizationProvider.class);
        OrganizationModel org = orgProvider.getByMember(user).findFirst().orElse(null);
        if (org == null) return null;

        GroupModel orgGroup = realm.getTopLevelGroupsStream()
                .filter(g -> matchesOrg(g, org))
                .findFirst()
                .orElse(null);
        if (orgGroup == null) return new AutomJoiningContext(org.getName(), null);

        Set<String> userGroupIds = user.getGroupsStream()
                .map(GroupModel::getId)
                .collect(Collectors.toSet());

        GroupModel projectGroup = orgGroup.getSubGroupsStream(0, 500)
                .filter(g -> !g.getName().equalsIgnoreCase("admins") && !g.getName().equalsIgnoreCase("owners"))
                .filter(g -> userGroupIds.contains(g.getId())
                        || g.getSubGroupsStream(0, 50).anyMatch(sub -> userGroupIds.contains(sub.getId())))
                .findFirst()
                .orElse(null);

        String role = AutomRoleResolver.resolve(orgGroup, projectGroup, userGroupIds);
        Locale locale = session.getContext().resolveLocale(user);
        return new AutomJoiningContext(org.getName(), roleLabel(role, locale));
    }

    /**
     * Not a FreeMarker msg() key -- this string is composed server-side in Java,
     * baked into the automJoiningRole form attribute before the template ever
     * runs, so it needs its own small translation table here instead of relying
     * on messages_xx.properties (which only covers strings the .ftl itself emits).
     */
    private static String roleLabel(String role, Locale locale) {
        if (role == null) return null;
        String lang = locale == null ? "en" : locale.getLanguage();
        return switch (role) {
            case AutomRoleResolver.ORG_ADMIN -> switch (lang) {
                case "de" -> "Org-Admin";
                case "fr" -> "Administrateur d'organisation";
                case "it" -> "Amministratore organizzazione";
                default -> "Org admin";
            };
            case AutomRoleResolver.PROJECT_ADMIN -> switch (lang) {
                case "de" -> "Projektadmin";
                case "fr" -> "Administrateur de projet";
                case "it" -> "Amministratore progetto";
                default -> "Project admin";
            };
            case AutomRoleResolver.PROJECT_MEMBER -> switch (lang) {
                case "de" -> "Mitglied";
                case "fr" -> "Membre";
                case "it" -> "Membro";
                default -> "Member";
            };
            default -> null;
        };
    }

    /** Duplicated from PostOrgProjectSelectorAuthenticator — see its matchesOrg/normalize for why. */
    private static boolean matchesOrg(GroupModel group, OrganizationModel org) {
        String groupName = normalize(group.getName());
        return groupName.equals(normalize(org.getName())) || groupName.equals(normalize(org.getAlias()));
    }

    private static String normalize(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase(Locale.ROOT);
    }
}
