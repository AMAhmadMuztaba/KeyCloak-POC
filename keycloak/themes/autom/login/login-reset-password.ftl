<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Reset password — Autom</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/400.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/500.css">
    <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
    <#-- Keycloak re-renders THIS SAME template after a successful submission --
         LoginActionsService.sendPasswordReset() calls form().setSuccess(...) and
         redisplays login-reset-password.ftl rather than switching to a different
         page (info.ftl is only used for other flows, e.g. after an action-token
         link completes). message.type == 'success' is that "email sent" signal
         (confirmed against how this same realm's setSuccess()/setError() pattern
         already distinguishes message.type elsewhere in this theme, e.g. the
         alert-${message.type} classes used on login.ftl/the org pickers). This
         branch swaps in the design's "isSent" copy/state instead of KC's default
         static emailSentMessage text, since that default has no way to interpolate
         the address that was actually submitted. -->
    <div class="page">
        <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
        <div class="card-col">
        <div class="card">

            <#if message?has_content && message.type == 'success'>

            <div class="header">
                <h1 class="title">${msg("autom.resetPassword.sentTitle")}</h1>
                <p class="subtitle">${msg("autom.resetPassword.sentSubtitle", (auth.attemptedUsername)!'')}</p>
            </div>

            <div style="margin-top: 0.5rem;">
                <a href="${url.loginUrl}" class="btn-secondary" style="text-decoration:none;">${msg("autom.resetPassword.backToSignIn")}</a>
            </div>

            <#else>

            <div class="header">
                <h1 class="title">${msg("autom.resetPassword.title")}</h1>
                <p class="subtitle">${msg("autom.resetPassword.subtitle")}</p>
            </div>

            <#if messagesPerField.existsError('username')>
            <div class="error-banner" role="alert">
                ${kcSanitize(messagesPerField.get('username'))?no_esc}
            </div>
            </#if>

            <form id="kc-reset-password-form" action="${url.loginAction}" method="post">

                <div class="field">
                    <label for="username" class="label"><#if !realm.loginWithEmailAllowed>${msg("autom.resetPassword.label.username")}<#elseif !realm.registrationEmailAsUsername>${msg("autom.resetPassword.label.usernameOrEmail")}<#else>${msg("autom.resetPassword.label.email")}</#if></label>
                    <input
                        type="text"
                        id="username"
                        name="username"
                        value="${(auth.attemptedUsername!'')}"
                        class="input<#if messagesPerField.existsError('username')> input--error</#if>"
                        autocomplete="username"
                        autofocus
                        dir="ltr"
                    />
                </div>

                <button type="submit" class="btn-primary">${msg("autom.resetPassword.submit")}</button>
                <a href="${url.loginUrl}" class="btn-secondary" style="text-decoration:none; margin-top: 0.5rem;">${msg("autom.resetPassword.backToSignIn")}</a>

            </form>

            </#if>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
