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
    <div class="page">
        <div class="card">

            <div class="header">
                <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="logo">
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

                <div style="text-align: center; margin-top: 1.25rem;">
                    <a href="${url.loginUrl}" class="forgot-link">${msg("autom.resetPassword.backToSignIn")}</a>
                </div>

            </form>

            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
