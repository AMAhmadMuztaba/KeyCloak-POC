<#-- Shown when a stale/expired step is resubmitted -- most commonly the
     browser Back button during a multi-step login (org/project picker, MFA
     setup, password reset), reusing a page whose one-time code Keycloak has
     already moved past. This template didn't exist in this theme at all
     before, so it silently fell back to Keycloak's completely unstyled base
     theme (confirmed live: raw HTML, no fonts, no card) whenever this
     specific failure happened -- same class of gap as the missing
     login-otp.ftl earlier. Real, necessary Keycloak behavior (a stale code
     genuinely can't be replayed safely), just needed its own themed page. -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Session expired — Autom</title>
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
        <div class="card">

            <div class="header">
                <h1 class="title">${msg("autom.pageExpired.title")}</h1>
                <p class="subtitle">${msg("autom.pageExpired.subtitle")}</p>
            </div>

            <a href="${url.loginRestartFlowUrl}" class="btn-primary" style="text-decoration:none;">${msg("autom.pageExpired.restart")}</a>
            <a href="${url.loginAction}" class="btn-secondary" style="text-decoration:none; margin-top: 0.5rem;">${msg("autom.pageExpired.continue")}</a>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
