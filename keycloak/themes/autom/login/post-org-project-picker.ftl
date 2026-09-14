<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Select project · Autom</title>
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
      <h1>Select project</h1>
      <p>Choose a project within <strong>${orgName}</strong> to continue.</p>
    </div>

    <form id="kc-project-selection" action="${url.loginAction}" method="post">
      <div class="organization-card-grid">
        <#if projects?has_content>
          <#list projects as project>
          <button class="organization-card" type="submit" name="project" value="${project.id}">
            <span class="organization-icon" aria-hidden="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            </span>
            <span class="organization-card-content">
              <strong>${project.name}</strong>
            </span>
            <span class="organization-arrow" aria-hidden="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </span>
          </button>
          </#list>
        <#else>
          <div class="empty-state">
            No Keycloak project access is configured for this organisation. Contact an organisation administrator.
          </div>
        </#if>
      </div>
    </form>
  </div>
</body>
</html>
