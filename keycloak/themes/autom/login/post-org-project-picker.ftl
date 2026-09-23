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
    <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
    <div class="card-col">
    <div class="card card--wide">

      <#-- No eyebrow ("Step 2 of 2") on this page -- deliberately omitted. This
           authenticator (autom-post-org-project-selector) can be reached two
           ways: right after the org picker (a real step 2), or directly after
           password/OTP when the user's single org was auto-selected (a real
           step 1). The FTL context here only gets "orgName" and "projects" --
           there's no flag telling it which path was taken, and adding one
           means teaching the Java authenticator to look up the user's org
           count again and pass a new form attribute, which is a custom-SPI
           change (needs a provider rebuild/redeploy) rather than a template
           edit. Skipped rather than guess and risk mislabeling a real step 1
           as "Step 2 of 2". Same reasoning as the org picker's missing "Back"
           button below: this authenticator's action() only re-validates a
           submitted "project" value, it doesn't support stepping backward. -->
      <div class="header">
        <h1 class="title">${msg("autom.projectPicker.title")}</h1>
        <#-- Sign In.dc.html line 184: the org name sits in plain text inside the
             sentence, same weight/color as the rest of it -- no <strong>. -->
        <p class="subtitle">${msg("autom.projectPicker.subtitlePrefix")} ${orgName}${msg("autom.projectPicker.subtitleSuffix")}</p>
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
            <#-- No leading icon here -- Sign In.dc.html's project rows (scopeRow(),
                 the "isProject" sc-for) render just the label and trailing chevron,
                 with no badge (only the org picker's rows carry the initials
                 badge). Matched exactly rather than reusing the old folder icon. -->
            <button class="organization-card" type="submit" name="project" value="${project.id}">
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

    </div>
      <#include "language-switcher.ftl">
    </div>
  </div>
</body>
</html>
