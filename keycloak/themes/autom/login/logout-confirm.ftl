<#import "template.ftl" as layout>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Autom</title>
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
                <h1 class="title">${msg("logoutConfirmTitle")}</h1>
            </div>

            <p class="subtitle" style="text-align: center; margin-bottom: 1.5rem;">
                ${msg("logoutConfirmHeader")}
            </p>

            <form id="kc-logout-confirm-form" action="${url.logoutConfirmAction}" method="post">
                <input type="hidden" name="session_code" value="${logoutConfirm.code}">
                <button type="submit" class="btn-primary" name="confirmLogout" id="kc-logout">
                    ${msg("doLogout")}
                </button>
            </form>

            <#if !logoutConfirm.skipLink && (client.baseUrl)?has_content>
                <div style="text-align: center; margin-top: 1rem;">
                    <a href="${client.baseUrl}" class="forgot-link">${msg("backToApplication")}</a>
                </div>
            </#if>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>

    <script>
        // Same duplicate-submission guard as login.ftl -- see that file for why.
        document.getElementById('kc-logout-confirm-form').addEventListener('submit', function () {
            document.getElementById('kc-logout').disabled = true;
        });
    </script>
</body>
</html>
