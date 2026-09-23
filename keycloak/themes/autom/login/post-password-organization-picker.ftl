<#-- Rendered by the custom autom-post-password-org-selector authenticator when a
     user belongs to more than one enabled organisation (single-org users are
     auto-selected and never see this page -- see
     PostPasswordOrganizationSelectorAuthenticator.authenticate()). Since this
     page only ever shows up when there IS a real choice, "Step 1 of 2" is a
     safe, always-true label from this page's own perspective: whatever
     happens next is either the project picker (step 2) or straight through to
     the app if the chosen org turns out to have 0-1 projects -- exactly the
     same "best effort, can't see the future" approximation the design's own
     prototype uses (it also can't know a chosen org's project count before
     it's picked). No "Back to sign in" button: this authenticator's action()
     only re-validates a submitted "organization" value against the SAME
     picker -- there is no code path that resets the auth session back to the
     password step, and one isn't safe to fake in a template alone. -->
<#function automInitials name>
    <#local parts = name?trim?split(" ")>
    <#local result = "">
    <#list parts as part>
        <#if part?length gt 0 && result?length lt 2>
            <#local result = result + part?substring(0, 1)>
        </#if>
    </#list>
    <#return result?upper_case>
</#function>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Select organisation — Autom</title>
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

      <div class="header">
        <span class="eyebrow">${msg("autom.orgPicker.eyebrow")}</span>
        <h1 class="title">${msg("autom.orgPicker.title")}</h1>
        <p class="subtitle">${msg("autom.orgPicker.subtitle")}</p>
      </div>

      <#if message?has_content>
        <div class="alert alert-${message.type}">
          ${message.summary?no_esc}
        </div>
      </#if>

      <form id="kc-org-selection" action="${url.loginAction}" method="post">
        <div class="organization-card-grid">
          <#list organizations as organization>
            <#assign orgProjectCount = (organizationProjectCounts[organization.id])!0>
            <button class="organization-card" type="submit" name="organization" value="${organization.alias}">
              <span class="organization-icon" aria-hidden="true">${automInitials(organization.name)}</span>
              <span class="organization-card-content">
                <strong>${organization.name}</strong>
                <small>
                  <#if orgProjectCount == 0>${msg("autom.orgPicker.projectCountZero")}<#elseif orgProjectCount == 1>${msg("autom.orgPicker.projectCountOne")}<#else>${msg("autom.orgPicker.projectCountMany", orgProjectCount)}</#if>
                </small>
              </span>
              <span class="organization-arrow" aria-hidden="true">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </span>
            </button>
          </#list>
        </div>
      </form>

    </div>
      <#include "language-switcher.ftl">
    </div>
  </div>
</body>
</html>
