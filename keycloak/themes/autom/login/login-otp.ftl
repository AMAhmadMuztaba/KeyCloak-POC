<#-- Renders for the standard `auth-otp-form` execution -- the step a returning
     user with an authenticator already enrolled sees on every sign-in once
     their password is accepted (Sign In.dc.html's "isMfa" step). This is
     DIFFERENT from login-config-totp.ftl, which is enrolment (first-time
     setup, onboarding step 3 / a mandatory-MFA org's next login). Before this
     file existed, this step silently fell back to Keycloak's unstyled base
     theme, since `autom` only overrides what it explicitly ships. -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Verification code — Autom</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/400.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/500.css">
    <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
    <#-- Mask the attempted username the same way the design's mask() helper does:
         first char + "•••" + everything from "@" onward. auth.attemptedUsername is
         the same binding login-reset-password.ftl already relies on elsewhere in
         this theme. No eyebrow ("Step 2 of 2") is rendered on this page -- see the
         report for why: live-checked this realm's actual authentication-execution
         order (autom-post-auth-selectors is CONDITIONAL, index 2, AFTER the 2FA
         CONDITIONAL at index 1, both inside "forms"), which means this OTP step
         always runs right after the password step but BEFORE the org/project
         picker steps for any user who has both 2FA and multi-org/project
         membership. So "of 2" is only true for a user with no org/project step
         after this one -- it would be actively wrong (2 of 4, 2 of 3) for anyone
         else, and this template has no access to the user's organisation/project
         membership counts to compute the real total (that data only exists inside
         the separate autom-post-password-org-selector / autom-post-org-project-
         selector authenticators, not in auth-otp-form's own FTL context). -->
    <#assign automRawUsername = (auth.attemptedUsername)!''>
    <#if automRawUsername?has_content && automRawUsername?index_of('@') gt 0>
        <#assign automMaskedUsername = automRawUsername?substring(0,1) + "•••" + automRawUsername?substring(automRawUsername?index_of('@'))>
    <#elseif automRawUsername?has_content>
        <#assign automMaskedUsername = automRawUsername>
    <#else>
        <#assign automMaskedUsername = msg("autom.otp.fallbackAccount")>
    </#if>
    <div class="page">
        <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
        <div class="card-col">
        <div class="card">

            <div class="header">
                <h1 class="title">${msg("autom.otp.title")}</h1>
                <p class="subtitle">${msg("autom.otp.subtitle", automMaskedUsername)}</p>
            </div>

            <#if messagesPerField.existsError('totp')>
            <div class="error-banner" role="alert">
                ${kcSanitize(messagesPerField.get('totp'))?no_esc}
            </div>
            </#if>

            <form id="kc-otp-login-form" action="${url.loginAction}" method="post">

                <#if otpLogin.userOtpCredentials?size gt 1>
                <div class="field">
                    <label class="label">${msg("autom.otp.deviceLabel")}</label>
                    <#list otpLogin.userOtpCredentials as otpCredential>
                        <label style="display:flex; align-items:center; gap:8px; margin-top:6px; font: 400 14px/21px var(--n-font-sans); color: var(--n-foreground);">
                            <input
                                type="radio"
                                name="selectedCredentialId"
                                value="${otpCredential.id}"
                                style="width:16px; height:16px; margin:0; accent-color: var(--n-primary);"
                                <#if otpCredential.id == otpLogin.selectedCredentialId>checked="checked"</#if>
                            />
                            ${otpCredential.userLabel}
                        </label>
                    </#list>
                </div>
                </#if>

                <div class="field">
                    <label for="otp" class="label">${msg("autom.otp.codeLabel")}</label>
                    <input
                        type="text"
                        id="otp"
                        name="otp"
                        autocomplete="one-time-code"
                        inputmode="numeric"
                        class="input<#if messagesPerField.existsError('totp')> input--error</#if>"
                        dir="ltr"
                        autofocus
                    />
                </div>

                <#-- No "Remember me on this device" checkbox and no "Back" button here --
                     both were in the design's isMfa state, and both were deliberately
                     skipped rather than added as non-functional controls:

                     - Remember me: Keycloak's rememberMe flag is captured ONLY by the
                       credential-collecting authenticator (auth-username-password-form,
                       rendered by login.ftl) when it processes its own form submission.
                       auth-otp-form's own action() validates the OTP code and does not
                       read a "rememberMe" request parameter at all, so a second checkbox
                       here would not be wired to anything real -- it just wouldn't do
                       what it visually promises. The realm-wide choice made on the
                       password page (see login.ftl) already covers the whole session.

                     - Back: live-checked this realm's actual flow ("Browser - Conditional
                       2FA" subflow, level 1): OTP Form is the only ENABLED alternative
                       (WebAuthn and Recovery Code are both DISABLED), so stock Keycloak
                       won't even offer its own "try another way" link here, and there is
                       no built-in mechanism to step an in-progress auth session back to a
                       REQUIRED authenticator (auth-username-password-form) that already
                       succeeded. Implementing a working back action would mean writing a
                       new custom authenticator/flow behavior, not a template change --
                       out of scope for this pass per the brief's own guidance to skip
                       custom-SPI-touching changes rather than ship a dead button. -->

                <button type="submit" class="btn-primary" name="login" id="kc-login">${msg("autom.otp.verify")}</button>

            </form>

            <p class="footer-note">${msg("autom.otp.footerNote")}</p>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
