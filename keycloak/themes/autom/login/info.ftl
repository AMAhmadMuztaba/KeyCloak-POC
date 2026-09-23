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
    <#-- An action-token flow (onboarding, email verify, etc.) just finished --
         continue straight to the app instead of making the user click "Back
         to Application". The app immediately detects no session and redirects
         to a FRESH Keycloak login (prompt: 'login' -- see main.tsx) itself.
         Tried redirecting straight to url.loginUrl instead (skipping this hop
         entirely), but that reuses the ORIGINAL action-token flow's auth
         session, which Keycloak has already cleaned up by this point --
         Keycloak errors with "Restart login cookie not found" instead of
         showing a login form. pageRedirectUri is the only reliable target here. -->
    <#if !skipLink?? && pageRedirectUri?has_content>
    <meta http-equiv="refresh" content="0; url=${pageRedirectUri}">
    <script>window.location.replace(${pageRedirectUri?js_string?no_esc});</script>
    </#if>
</head>
<body>
    <div class="page">
        <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
        <div class="card-col">
        <div class="card">

            <#-- confirmExecutionOfActions: the confirmation Keycloak shows before
                 starting required actions that came from a link (an invite/reset
                 email, or an app asking to redo one) rather than a live password
                 login -- it hasn't just verified the person, so it asks first.
                 Real, necessary step; not something we can skip. Given dedicated
                 copy here instead of Keycloak's own generic
                 "Perform the following action(s)" + message.summary, whose exact
                 wording we don't control and shouldn't build a sentence around. -->
            <#if messageHeader?? && messageHeader == "confirmExecutionOfActions">
            <div class="header">
                <h1 class="title">${msg("autom.confirmActions.title")}</h1>
                <p class="subtitle">${msg("autom.confirmActions.subtitle")}</p>
            </div>

            <#if requiredActions??>
            <p class="subtitle" style="text-align: center; margin-bottom: 1.5rem;">
                <#list requiredActions><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></#list>
            </p>
            </#if>

            <#if !skipLink?? && actionUri?has_content>
                <div style="text-align: center;"><a href="${actionUri}" class="btn-primary" style="display:inline-flex; width:auto; padding: 0 1.5rem; text-decoration:none;">${msg("autom.confirmActions.continue")}</a></div>
            </#if>

            <#elseif pageRedirectUri?has_content>

            <#-- An action-token flow (onboarding, email verify, TOTP setup, etc.)
                 just finished and the <script> above is already redirecting --
                 this is only visible for the instant before that fires (or if JS
                 is blocked). Dedicated copy instead of Keycloak's generic
                 message.summary, which wasn't written for this specific moment. -->
            <div class="header">
                <h1 class="title">${msg("autom.redirecting.title")}</h1>
                <p class="subtitle">${msg("autom.redirecting.subtitle")}</p>
            </div>

            <#if !skipLink??>
                <div style="text-align: center;"><a href="${pageRedirectUri}" class="btn-primary" style="display:inline-flex; width:auto; padding: 0 1.5rem; text-decoration:none;">${msg("autom.redirecting.continue")}</a></div>
            </#if>

            <#else>

            <#-- message.summary is the one real piece of text Keycloak gives this
                 page for every OTHER call site. When messageHeader is also set,
                 it's a distinct short label -- summary belongs in the subtitle.
                 When it's NOT set, summary IS the only content Keycloak gave us,
                 so it goes in the title instead -- showing it a second time in
                 the subtitle would just repeat the same sentence twice. -->
            <div class="header">
                <h1 class="title">
                    <#if messageHeader??>${kcSanitize(msg("${messageHeader}"))?no_esc}<#else>${message.summary}</#if>
                </h1>
            </div>

            <#-- No <b> around the action list: bolding it put the whole subtitle at
                 the same visual weight as the title above it, losing the
                 title/subtitle hierarchy the rest of this theme relies on. -->
            <#if messageHeader??>
            <p class="subtitle" style="text-align: center; margin-bottom: 1.5rem;">
                ${message.summary}<#if requiredActions??><#list requiredActions>: <#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></#list></#if>
            </p>
            <#elseif requiredActions??>
            <p class="subtitle" style="text-align: center; margin-bottom: 1.5rem;">
                <#list requiredActions><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></#list>
            </p>
            </#if>

            <#if !skipLink??>
                <#if actionUri?has_content>
                    <div style="text-align: center;"><a href="${actionUri}" class="btn-primary" style="display:inline-flex; width:auto; padding: 0 1.5rem; text-decoration:none;">${msg("proceedWithAction")}</a></div>
                <#elseif (client.baseUrl)?has_content>
                    <div style="text-align: center;"><a href="${client.baseUrl}" class="btn-primary" style="display:inline-flex; width:auto; padding: 0 1.5rem; text-decoration:none;">${msg("backToApplication")}</a></div>
                </#if>
            </#if>

            </#if>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>
</body>
</html>
