<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Select organisation · Autom</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
  <div id="kc-container">

    <div class="logo-wrap">
      <img src="${url.resourcesPath}/img/autom-primary-logo.svg" alt="Autom" />
    </div>

    <#if message?has_content>
      <div class="alert alert-${message.type}">
        ${message.summary?no_esc}
      </div>
    </#if>

    <div class="picker-heading">
      <h1>Select organisation</h1>
      <p>Your session and access will be scoped to the selected organisation.</p>
    </div>

    <form id="kc-org-selection" action="${url.loginAction}" method="post">
      <div class="organization-card-grid">
        <#list organizations as organization>
          <button class="organization-card" type="submit" name="organization" value="${organization.alias}">
            <span class="organization-icon" aria-hidden="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="7" width="20" height="14" rx="2"/>
                <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
              </svg>
            </span>
            <span class="organization-card-content">
              <strong>${organization.name}</strong>
              <small>${organization.alias}</small>
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
</body>
</html>
