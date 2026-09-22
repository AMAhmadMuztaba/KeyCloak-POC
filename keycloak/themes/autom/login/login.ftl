<#import "template.ftl" as layout>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sign in — Autom</title>
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
        <h1 class="title">${msg("autom.login.title")}</h1>
        <p class="subtitle">${msg("autom.login.subtitle")}</p>
      </div>

      <#if message?has_content>
        <div class="alert alert-${message.type}">
          ${message.summary?no_esc}
        </div>
      </#if>

      <form id="kc-form-login" action="${url.loginAction}" method="post">

        <#-- onfocus="this.select()" on both fields below: autocomplete="username"/
             "current-password" (needed for password manager support) means the
             browser can silently fill a value into these fields, and that
             inserted text isn't always left selected the way a manual autofill
             pick normally is. Without selecting on focus, typing over an
             autofilled value inserts at the cursor instead of replacing it --
             confirmed live: clicking the field and typing "alice@x.com" over an
             autofilled "alice@x.com" produced "alice@x.comalice@x.com", silently
             submitted, and always failed as wrong credentials. Selecting the
             existing value on focus means any subsequent typing replaces it,
             regardless of how it got there. -->
        <div class="field">
          <label for="username" class="label">${msg("autom.login.emailLabel")}</label>
          <input
            id="username"
            name="username"
            type="text"
            class="input"
            value="${(login.username!'')}"
            autocomplete="username"
            placeholder="${msg("autom.login.emailPlaceholder")}"
            autofocus
            onfocus="this.select()"
          />
        </div>

        <div class="field">
          <label for="password" class="label">${msg("autom.login.passwordLabel")}</label>
          <div class="password-wrap">
            <input
              id="password"
              name="password"
              type="password"
              class="input"
              autocomplete="current-password"
              placeholder="${msg("autom.login.passwordPlaceholder")}"
              onfocus="this.select()"
            />
            <button type="button" class="toggle-password" onclick="togglePassword()" aria-label="Toggle password visibility">
              <svg id="eye-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
              <svg id="eye-off-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            </button>
          </div>
        </div>

        <#if realm.resetPasswordAllowed>
          <div style="text-align: right; margin-top: -0.5rem; margin-bottom: 1rem;">
            <a href="${url.loginResetCredentialsUrl}" class="forgot-link">${msg("autom.login.forgotPassword")}</a>
          </div>
        </#if>

        <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>

        <button type="submit" class="btn-primary" name="login">
          ${msg("autom.login.submit")}
        </button>

      </form>

      <#include "language-switcher.ftl">
    </div>
  </div>

  <script>
    function togglePassword() {
      var input = document.getElementById('password');
      var eyeIcon = document.getElementById('eye-icon');
      var eyeOffIcon = document.getElementById('eye-off-icon');
      if (input.type === 'password') {
        input.type = 'text';
        eyeIcon.style.display = 'none';
        eyeOffIcon.style.display = 'block';
      } else {
        input.type = 'password';
        eyeIcon.style.display = 'block';
        eyeOffIcon.style.display = 'none';
      }
    }

    // Without this, a double-click, an Enter keypress that lands while a
    // browser autofill suggestion is also submitting, or any other double
    // trigger sends two (or more) near-simultaneous POSTs for what was one
    // user action. Each extra POST counts as its own failed/quick attempt
    // toward brute-force detection, so a single genuine login attempt could
    // trip the "quick retry" lockout on its own. Disabling the button on the
    // form's first submit prevents any further click from firing a second
    // request; the real POST still goes through normally.
    //
    // The disable is deferred with setTimeout(..., 0) rather than run
    // synchronously in this handler -- disabling a <button type="submit">
    // while its own 'submit' event is still being processed is a known
    // browser footgun that can cancel the in-flight submission itself
    // instead of just blocking a second one, so the real click silently did
    // nothing and needed 2-3 tries with zero error, zero server log entry to
    // show for it. Deferring by one tick lets the browser finish acting on
    // this submission first; the button is still disabled before any human
    // could physically click it again.
    document.getElementById('kc-form-login').addEventListener('submit', function () {
      setTimeout(function () {
        document.querySelector('#kc-form-login button[type="submit"]').disabled = true;
      }, 0);
    });
  </script>
</body>
</html>
