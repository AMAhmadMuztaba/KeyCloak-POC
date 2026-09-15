<#import "template.ftl" as layout>
<#import "password-commons.ftl" as passwordCommons>
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
        <div class="card card--wide">

            <div class="header">
                <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="logo">
            </div>

            <div class="step-progress" role="group" aria-label="${msg("autom.totp.eyebrow")}">
                <span class="is-done"></span>
                <span class="is-done"></span>
                <span class="is-current"></span>
            </div>

            <div class="header">
                <p class="eyebrow">${msg("autom.totp.eyebrow")}</p>
                <h1 class="title">${msg("autom.totp.title")}</h1>
                <#if automSkippable??>
                    <p class="subtitle">${msg("autom.totp.subtitleRecommended")}</p>
                <#else>
                    <p class="subtitle">${msg("autom.totp.subtitleRequired")}</p>
                </#if>
            </div>

            <#if messagesPerField.existsError('totp','userLabel')>
            <div class="error-banner" role="alert">
                ${kcSanitize(messagesPerField.getFirstError('totp','userLabel'))?no_esc}
            </div>
            </#if>

            <ol class="totp-steps">
                <li>
                    <#if mode?? && mode = "manual">
                        <p class="totp-step-label">${msg("autom.totp.cantScan")}</p>
                        <p class="totp-secret-key" id="kc-totp-secret-key">${totp.totpSecretEncoded}</p>
                        <a href="${totp.qrUrl}" id="mode-barcode" class="forgot-link">${msg("autom.totp.showQr")}</a>
                    <#else>
                        <img id="kc-totp-secret-qr-code" class="totp-qr" src="data:image/png;base64, ${totp.totpSecretQrCode}" alt="QR code for authenticator setup">
                        <p class="totp-step-label" style="margin-top: 0.75rem; margin-bottom: 0;">${msg("autom.totp.scanInstruction")}</p>
                        <a href="${totp.manualUrl}" id="mode-manual" class="forgot-link">${msg("autom.totp.cantScan")}</a>
                    </#if>
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

                <@passwordCommons.logoutOtherSessions/>

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

            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
