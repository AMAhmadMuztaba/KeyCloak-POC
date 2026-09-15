<#import "template.ftl" as layout>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Verify email — Autom</title>
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
                <h1 class="title">${msg("emailVerifyTitle")}</h1>
                <p class="subtitle">
                    <#if verifyEmail??>
                        ${msg("emailVerifyInstruction1", verifyEmail)}
                    <#else>
                        ${msg("emailVerifyInstruction4", user.email)}
                    </#if>
                </p>
            </div>

            <#if isAppInitiatedAction??>
                <form id="kc-verify-email-form" action="${url.loginAction}" method="post">
                    <#if verifyEmail??>
                        <button class="btn-primary" type="submit">${msg("emailVerifyResend")}</button>
                    <#else>
                        <button class="btn-primary" type="submit">${msg("emailVerifySend")}</button>
                    </#if>
                    <button class="btn-secondary" type="submit" name="cancel-aia" value="true" formnovalidate style="margin-top: 0.5rem;">${msg("doCancel")}</button>
                </form>
            <#else>
                <p class="subtitle" style="text-align: center;">
                    ${msg("emailVerifyInstruction2")}<br/>
                    <a href="${url.loginAction}" class="forgot-link">${msg("doClickHere")}</a> ${msg("emailVerifyInstruction3")}
                </p>
            </#if>

            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
