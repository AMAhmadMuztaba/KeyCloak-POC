package com.selise.autom.keycloak;

import jakarta.enterprise.inject.Vetoed;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.OPTIONS;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import java.util.Set;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.keycloak.models.GroupModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.OrganizationModel;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.UserSessionModel;
import org.keycloak.organization.OrganizationProvider;
import org.keycloak.services.managers.AppAuthManager;

/**
 * KC realm resource that lets the React app switch the active project without
 * a full login-page redirect.
 *
 * Endpoint: PUT /realms/{realm}/autom/switch-project
 * Body:     { "projectId": "<Keycloak group UUID>", "organizationId": "<optional UUID>" }
 * Auth:     Bearer access token (autom-app client)
 *
 * Updates autom.project.group.id and autom.project.name on the user session.
 * The caller must follow up with keycloak.updateToken(-1) to get a fresh JWT
 * that reflects the new project_id claim.
 */
@Vetoed
@Path("/")
public class AutomProjectSwitchResource {

    private final KeycloakSession session;

    public AutomProjectSwitchResource(KeycloakSession session) {
        this.session = session;
    }

    /** CORS preflight for cross-origin PUT from the React app. */
    @OPTIONS
    @Path("switch-project")
    public Response preflight(@Context HttpHeaders headers) {
        String origin = headers.getHeaderString("Origin");
        return corsOk(Response.ok(), origin).build();
    }

    /** CORS preflight for the Keycloak-authoritative project catalogue. */
    @OPTIONS
    @Path("projects")
    public Response projectsPreflight(@Context HttpHeaders headers) {
        return corsOk(Response.ok(), headers.getHeaderString("Origin")).build();
    }

    @PUT
    @Path("switch-project")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    public Response switchProject(@Context HttpHeaders headers, SwitchRequest body) {
        String origin = headers.getHeaderString("Origin");
        RealmModel realm = session.getContext().getRealm();

        // Use a bean rather than a Java record: the RESTEasy/Jackson stack in
        // deployed Keycloak images does not consistently register record
        // parameter metadata, which makes it reject an otherwise valid JSON
        // request with a generic 400 before this resource can respond.
        if (body == null || body.projectId == null || body.projectId.isBlank()) {
            return corsOk(Response.status(400).entity("{\"error\":\"projectId required\"}"), origin).build();
        }

        var auth = new AppAuthManager.BearerTokenAuthenticator(session)
                .setRealm(realm)
                .authenticate();

        if (auth == null) {
            return corsOk(Response.status(401).entity("{\"error\":\"unauthenticated\"}"), origin).build();
        }

        UserModel user = auth.getUser();
        UserSessionModel userSession = auth.getSession();

        // A caller may switch both organisation and project in one atomic request.
        // The target organization is always checked against native KC membership.
        String orgId = body.organizationId;
        if (orgId == null || orgId.isBlank()) {
            orgId = userSession.getNote(PostPasswordOrganizationSelectorAuthenticator.ACTIVE_ORGANIZATION_ID_NOTE);
        }
        if (orgId == null || orgId.isBlank()) {
            orgId = userSession.getNote(OrganizationModel.ORGANIZATION_ATTRIBUTE);
        }
        if (orgId == null) {
            return corsOk(Response.status(422).entity("{\"error\":\"no org in session\"}"), origin).build();
        }
        OrganizationModel org = session.getProvider(OrganizationProvider.class).getById(orgId);
        if (org == null) {
            return corsOk(Response.status(422).entity("{\"error\":\"org not found\"}"), origin).build();
        }
        boolean isMember = session.getProvider(OrganizationProvider.class)
                .getByMember(user)
                .anyMatch(candidate -> candidate.getId().equals(org.getId()) && candidate.isEnabled());
        if (!isMember) {
            return corsOk(Response.status(403).entity("{\"error\":\"organization access denied\"}"), origin).build();
        }

        // Find the org's top-level KC group.
        GroupModel orgGroup = realm.getTopLevelGroupsStream()
                .filter(g -> matchesOrganizationGroup(g, org))
                .findFirst().orElse(null);
        if (orgGroup == null) {
            return corsOk(Response.status(422).entity("{\"error\":\"org group not found\"}"), origin).build();
        }

        // Resolve by immutable Keycloak group ID. Names are mutable and are not
        // unique enough to be an authorization input.
        GroupModel projectGroup = orgGroup.getSubGroupsStream(0, 500)
                .filter(g -> g.getId().equals(body.projectId))
                .findFirst().orElse(null);
        if (projectGroup == null) {
            return corsOk(Response.status(404).entity("{\"error\":\"project not found\"}"), origin).build();
        }

        // Verify the user has access to this project group.
        Set<String> userGroupIds = user.getGroupsStream()
                .map(GroupModel::getId)
                .collect(Collectors.toSet());

        boolean hasOrgWideAccess = userGroupIds.contains(orgGroup.getId())
                || orgGroup.getSubGroupsStream(0, 50)
                        .filter(g -> g.getName().equalsIgnoreCase("admins")
                                  || g.getName().equalsIgnoreCase("owners"))
                        .anyMatch(g -> userGroupIds.contains(g.getId()));
        boolean hasAccess = hasOrgWideAccess
                || userGroupIds.contains(projectGroup.getId())
                || projectGroup.getSubGroupsStream(0, 50)
                               .anyMatch(sub -> userGroupIds.contains(sub.getId()));
        if (!hasAccess) {
            return corsOk(Response.status(403).entity("{\"error\":\"access denied\"}"), origin).build();
        }

        // The initializer maps these server-side notes to signed JWT claims.
        userSession.setNote(OrganizationModel.ORGANIZATION_ATTRIBUTE, org.getId());
        userSession.setNote(PostPasswordOrganizationSelectorAuthenticator.ACTIVE_ORGANIZATION_ID_NOTE, org.getId());
        userSession.setNote(PostOrgProjectSelectorAuthenticator.PROJECT_ID_NOTE, projectGroup.getId());
        userSession.setNote(PostOrgProjectSelectorAuthenticator.PROJECT_NAME_NOTE, projectGroup.getName());

        return corsOk(Response.noContent(), origin).build();
    }

    /**
     * Keycloak-authoritative project catalogue for the workspace picker. The
     * browser never derives access from its own cached portal records.
     */
    @GET
    @Path("projects")
    @Produces(MediaType.APPLICATION_JSON)
    public Response projects(@Context HttpHeaders headers, @QueryParam("organizationId") String organizationId) {
        String origin = headers.getHeaderString("Origin");
        RealmModel realm = session.getContext().getRealm();
        var auth = new AppAuthManager.BearerTokenAuthenticator(session).setRealm(realm).authenticate();
        if (auth == null) return corsOk(Response.status(401).entity("{\"error\":\"unauthenticated\"}"), origin).build();
        if (organizationId == null || organizationId.isBlank())
            return corsOk(Response.status(400).entity("{\"error\":\"organizationId required\"}"), origin).build();

        UserModel user = auth.getUser();
        OrganizationModel org = session.getProvider(OrganizationProvider.class).getById(organizationId);
        boolean isMember = org != null && session.getProvider(OrganizationProvider.class).getByMember(user)
                .anyMatch(candidate -> candidate.getId().equals(org.getId()) && candidate.isEnabled());
        if (!isMember) return corsOk(Response.status(403).entity("{\"error\":\"organization access denied\"}"), origin).build();

        GroupModel orgGroup = realm.getTopLevelGroupsStream()
                .filter(g -> matchesOrganizationGroup(g, org))
                .findFirst().orElse(null);
        if (orgGroup == null) return corsOk(Response.ok(List.of()), origin).build();

        Set<String> groups = user.getGroupsStream().map(GroupModel::getId).collect(Collectors.toSet());
        boolean orgWide = groups.contains(orgGroup.getId()) || orgGroup.getSubGroupsStream(0, 50)
                .filter(g -> g.getName().equalsIgnoreCase("admins") || g.getName().equalsIgnoreCase("owners"))
                .anyMatch(g -> groups.contains(g.getId()));
        List<Map<String, String>> result = orgGroup.getSubGroupsStream(0, 500)
                .filter(g -> !g.getName().equalsIgnoreCase("admins") && !g.getName().equalsIgnoreCase("owners"))
                .filter(g -> orgWide || groups.contains(g.getId()) || g.getSubGroupsStream(0, 50).anyMatch(s -> groups.contains(s.getId())))
                .sorted((a, b) -> a.getName().compareToIgnoreCase(b.getName()))
                .map(g -> Map.of("id", g.getId(), "name", g.getName()))
                .collect(Collectors.toList());
        return corsOk(Response.ok(result), origin).build();
    }

    private static Response.ResponseBuilder corsOk(Response.ResponseBuilder b, String origin) {
        if (isAllowedOrigin(origin)) {
            b.header("Access-Control-Allow-Origin", origin)
             .header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
             .header("Access-Control-Allow-Headers", "Authorization, Content-Type")
             .header("Access-Control-Max-Age", "86400")
             .header("Vary", "Origin");
        }
        return b;
    }

    private static boolean isAllowedOrigin(String origin) {
        if (origin == null) return false;
        return origin.equals("http://localhost:5173")
                || origin.equals("http://localhost:3000")
                || origin.matches("https://[a-zA-Z0-9-]+\\.seliselocal\\.com");
    }

    /** Legacy group names often use '_' while KC organization aliases use '-'. */
    private static boolean matchesOrganizationGroup(GroupModel group, OrganizationModel organization) {
        String groupName = normalize(group.getName());
        return groupName.equals(normalize(organization.getName()))
                || groupName.equals(normalize(organization.getAlias()));
    }

    private static String normalize(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase(java.util.Locale.ROOT);
    }

    public static final class SwitchRequest {
        public String projectId;
        public String organizationId;

        public SwitchRequest() { }
    }
}
