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
                <h1 class="title">${kcSanitize(msg("errorTitle"))?no_esc}</h1>
            </div>

            <div class="error-banner" role="alert">
                ${kcSanitize(message.summary)?no_esc}
            </div>

            <#if traceId??>
                <p class="subtitle" id="traceId" style="margin-bottom: 1.25rem;">${msg("traceIdSupportMessage", traceId)}</p>
            </#if>

            <#if !skipLink?? && client?? && client.baseUrl?has_content>
                <div style="text-align: center;">
                    <a id="backToApplication" href="${client.baseUrl}" class="forgot-link">${msg("backToApplication")}</a>
                </div>
            </#if>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
