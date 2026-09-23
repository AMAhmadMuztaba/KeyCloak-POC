<#import "template.ftl" as layout>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Two-factor authentication — Autom</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/400.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/500.css">
    <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
    <div class="page">
        <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
        <div class="card-col">
        <div class="card card--wide">

            <div class="step-progress" role="group" aria-label="${msg("autom.totp.eyebrow")}">
                <span class="is-done"></span>
                <span class="is-done"></span>
                <span class="is-current"></span>
            </div>

            <div class="header">
                <p class="eyebrow">${msg("autom.totp.eyebrow")}</p>
                <#if automSkippable??>
                    <h1 class="title">${msg("autom.totp.title")}</h1>
                <#else>
                    <h1 class="title">${msg("autom.totp.titleRequired")}</h1>
                    <p class="subtitle">${msg("autom.totp.subtitleRequired")}</p>
                </#if>
            </div>

            <#if messagesPerField.existsError('totp','userLabel')>
            <div class="error-banner" role="alert">
                ${kcSanitize(messagesPerField.getFirstError('totp','userLabel'))?no_esc}
            </div>
            </#if>

            <#-- Onboarding.dc.html (MFA step, "Can't scan it? Enter this setup
                 key") shows the QR code and the manual setup key together,
                 always -- the key is "the accessible equivalent of the QR
                 (WCAG 1.1.1), not a fallback" (Onboarding Stories.md, Story
                 O3). Previously this toggled between QR-only and key-only via
                 a mode= link/page reload; both totp.totpSecretQrCode and
                 totp.totpSecretEncoded are populated on this context
                 regardless of mode, so showing both needs no new bindings or
                 message keys -- just drop the toggle. -->
            <ol class="totp-steps">
                <li>
                    <img id="kc-totp-secret-qr-code" class="totp-qr" src="data:image/png;base64, ${totp.totpSecretQrCode}" alt="QR code for authenticator setup">
                    <p class="totp-step-label" style="margin-top: 0.75rem; margin-bottom: 0;">${msg("autom.totp.scanInstruction")}</p>
                    <p class="totp-step-label" style="margin-top: 0.75rem;">${msg("autom.totp.cantScan")}</p>
                    <div class="totp-secret-row">
                        <span class="totp-secret-key" id="kc-totp-secret-key">${totp.totpSecretEncoded}</span>
                        <button type="button" id="copy-secret-btn" class="btn-copy-secret" onclick="copyTotpSecret()">${msg("autom.totp.copy")}</button>
                    </div>
                </li>
            </ol>

            <form action="${url.loginAction}" id="kc-totp-settings-form" method="post">

                <div class="field">
                    <label for="totp" class="label">${msg("autom.totp.codeLabel")}</label>
                    <input
                        type="text"
                        id="totp"
                        name="totp"
                        autocomplete="one-time-code"
                        inputmode="numeric"
                        class="input<#if messagesPerField.existsError('totp')> input--error</#if>"
                        dir="ltr"
                        autofocus
                    />
                </div>

                <div class="field">
                    <label for="userLabel" class="label">${msg("autom.totp.deviceLabel")}<#if totp.otpCredentials?size gte 1> *</#if></label>
                    <input
                        type="text"
                        id="userLabel"
                        name="userLabel"
                        autocomplete="off"
                        class="input<#if messagesPerField.existsError('userLabel')> input--error</#if>"
                        dir="ltr"
                    />
                </div>

                <input type="hidden" id="totpSecret" name="totpSecret" value="${totp.totpSecret}" />
                <#if mode??><input type="hidden" id="mode" name="mode" value="${mode}"/></#if>

                <#-- automSkippable is set only by the custom autom-optional-totp provider
                     (AutomOptionalTotp.java), which intercepts cancel-aia itself before
                     delegating to stock UpdateTotp validation. This same page also renders
                     for stock CONFIGURE_TOTP directly (MFA-mandatory orgs -- see
                     AutomMfaEnforcementAuthenticator), which never sets this attribute and
                     never honors cancel-aia on a queued action -- Skip must not show there. -->
                <button type="submit" class="btn-primary" id="saveTOTPBtn">${msg("autom.totp.verify")}</button>
                <#if automSkippable??>
                    <button type="submit" class="btn-secondary" id="cancelTOTPBtn" name="cancel-aia" value="true" style="margin-top: 0.5rem;">${msg("autom.totp.skip")}</button>
                </#if>

            </form>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>

    <script>
        var totpCopyLabel = "${msg("autom.totp.copy")?js_string}";
        var totpCopiedLabel = "${msg("autom.totp.copied")?js_string}";
        function copyTotpSecret() {
            var secret = document.getElementById('kc-totp-secret-key').textContent;
            var btn = document.getElementById('copy-secret-btn');
            var reset = function () { btn.textContent = totpCopyLabel; };
            if (navigator.clipboard) {
                navigator.clipboard.writeText(secret).catch(function () {});
            }
            btn.textContent = totpCopiedLabel;
            setTimeout(reset, 1600);
        }
    </script>
</body>
</html>
