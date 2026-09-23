package com.selise.autom.keycloak;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpRequest.BodyPublishers;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Base64;
import java.util.List;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.jboss.logging.Logger;
import org.keycloak.authentication.RequiredActionContext;
import org.keycloak.authentication.requiredactions.UpdateProfile;
import org.keycloak.authentication.RequiredActionProvider;
import org.keycloak.models.KeycloakSession;

/**
 * Extends stock UPDATE_PROFILE (never replaces it — registered under a new
 * provider id, same pattern as {@code autom-optional-totp}, so the built-in
 * "UPDATE_PROFILE" stays available for anything else that queues it) to add
 * an optional profile-picture upload, forwarded server-to-server to the .NET
 * API's internal endpoint (shared-secret auth — the user has no bearer token
 * yet mid-onboarding). TEMPORARY: MongoDB via that endpoint is a stand-in
 * until real object storage exists; swapping it needs no change on this side.
 *
 * Deliberately NOT a real multipart file field: a first attempt used
 * enctype="multipart/form-data" with a file input, which broke stock
 * UpdateProfile.processAction() outright — it (like everything else on this
 * form) reads fields via context.getHttpRequest().getDecodedFormParameters(),
 * and on this Keycloak/Quarkus version that call throws once any file part is
 * present in the request (confirmed live via a container stack trace,
 * RestEasy Reactive's FormData$FormValueImpl.getValue() choking on a
 * non-string part) — so firstName/lastName/email all came back empty
 * ("Please specify this field" x3) even though the request body had
 * ostensibly-fine values. Fix: the form stays plain url-encoded (its
 * original, working shape) and the picture travels as a base64 data URL in
 * an ordinary hidden field instead, read via the exact same
 * getDecodedFormParameters() call already proven to work for every other
 * field on this page.
 *
 * The picture is optional and best-effort: an invalid/oversized upload or a
 * failed call to the API is logged and swallowed, never blocks the profile
 * step — losing a picture is not worth stranding someone mid-onboarding.
 */
public class AutomOnboardingProfile extends UpdateProfile {

    private static final Logger LOG = Logger.getLogger(AutomOnboardingProfile.class);

    static final String PROVIDER_ID = "autom-onboarding-profile";

    private static final long MAX_PICTURE_BYTES = 2L * 1024 * 1024;
    private static final List<String> ALLOWED_CONTENT_TYPES = List.of("image/png", "image/jpeg", "image/webp");
    private static final Pattern DATA_URL = Pattern.compile("^data:([^;]+);base64,(.+)$", Pattern.DOTALL);

    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    private static final Properties INTERNAL_CONFIG = loadInternalConfig();

    @Override
    public void processAction(RequiredActionContext context) {
        try {
            handlePictureUpload(context);
        } catch (Exception e) {
            // Best-effort: never let a picture-upload problem block the profile step.
            LOG.warn("Profile picture upload failed, continuing without it", e);
        }
        super.processAction(context);
    }

    private void handlePictureUpload(RequiredActionContext context) {
        String dataUrl = context.getHttpRequest().getDecodedFormParameters().getFirst("profilePictureDataUrl");
        if (dataUrl == null || dataUrl.isBlank()) return;

        Matcher m = DATA_URL.matcher(dataUrl);
        if (!m.matches()) {
            LOG.warn("profilePictureDataUrl did not match the expected data: URL shape; ignoring");
            return;
        }
        String contentType = m.group(1);
        if (!ALLOWED_CONTENT_TYPES.contains(contentType)) return;

        byte[] bytes;
        try {
            bytes = Base64.getDecoder().decode(m.group(2));
        } catch (IllegalArgumentException e) {
            LOG.warn("profilePictureDataUrl had invalid base64 payload; ignoring", e);
            return;
        }
        if (bytes.length == 0 || bytes.length > MAX_PICTURE_BYTES) return;

        String baseUrl = INTERNAL_CONFIG.getProperty("api-base-url");
        String secret = INTERNAL_CONFIG.getProperty("profile-picture-shared-secret");
        if (baseUrl == null || baseUrl.isBlank() || secret == null || secret.isBlank()) {
            LOG.warn("autom-internal.properties missing api-base-url/profile-picture-shared-secret; skipping upload");
            return;
        }

        String userId = context.getUser().getId();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/api/internal/onboarding/profile-picture/" + userId))
                .header("Content-Type", contentType)
                .header("X-Internal-Secret", secret)
                .timeout(Duration.ofSeconds(10))
                .PUT(BodyPublishers.ofByteArray(bytes))
                .build();

        try {
            HttpResponse<Void> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.discarding());
            if (response.statusCode() / 100 != 2) {
                LOG.warnf("Profile picture upload for user %s returned HTTP %d", userId, response.statusCode());
            }
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            LOG.warn("Profile picture upload failed", e);
        }
    }

    private static Properties loadInternalConfig() {
        Properties props = new Properties();
        try (InputStream in = AutomOnboardingProfile.class.getClassLoader()
                .getResourceAsStream("autom-internal.properties")) {
            if (in != null) props.load(in);
        } catch (IOException e) {
            LOG.warn("Failed to load autom-internal.properties", e);
        }
        return props;
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getDisplayText() {
        return "Update Profile (Autom onboarding)";
    }

    @Override
    public RequiredActionProvider create(KeycloakSession session) {
        return this;
    }
}
