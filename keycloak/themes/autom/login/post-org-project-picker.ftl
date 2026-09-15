<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Select project — Autom</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/400.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/open-sauce-sans/500.css">
  <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
  <div class="page">
    <div class="card card--wide">

      <div class="header">
        <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="logo">
        <h1 class="title">${msg("autom.projectPicker.title")}</h1>
        <p class="subtitle">${msg("autom.projectPicker.subtitlePrefix")} <strong>${orgName}</strong> ${msg("autom.projectPicker.subtitleSuffix")}</p>
      </div>

      <#if message?has_content>
        <div class="alert alert-${message.type}">
          ${message.summary?no_esc}
        </div>
      </#if>

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
              ${msg("autom.projectPicker.emptyState")}
            </div>
          </#if>
        </div>
      </form>

      <#include "language-switcher.ftl">
    </div>
  </div>
</body>
</html>
