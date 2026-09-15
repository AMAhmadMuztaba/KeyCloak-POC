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
        <div class="card">

            <div class="header">
                <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="logo">
                <h1 class="title">
                    <#if messageHeader??>${kcSanitize(msg("${messageHeader}"))?no_esc}<#else>${message.summary}</#if>
                </h1>
            </div>

            <p class="subtitle" style="text-align: center; margin-bottom: 1.5rem;">
                ${message.summary}<#if requiredActions??><#list requiredActions>: <b><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></b></#list></#if>
            </p>

            <#if !skipLink??>
                <#if pageRedirectUri?has_content>
                    <div style="text-align: center;"><a href="${pageRedirectUri}" class="btn-primary" style="display:inline-flex; width:auto; padding: 0 1.5rem; text-decoration:none;">${msg("backToApplication")}</a></div>
                <#elseif actionUri?has_content>
                    <div style="text-align: center;"><a href="${actionUri}" class="btn-primary" style="display:inline-flex; width:auto; padding: 0 1.5rem; text-decoration:none;">${msg("proceedWithAction")}</a></div>
                <#elseif (client.baseUrl)?has_content>
                    <div style="text-align: center;"><a href="${client.baseUrl}" class="forgot-link">${msg("backToApplication")}</a></div>
                </#if>
            </#if>

            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
