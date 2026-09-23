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
    <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
    <div class="card-col">
    <div class="card">

      <div class="header">
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
            <#-- Inline text toggle (Show/Hide), per the design's password field --
                 replaces the previous eye-icon-swap button with the exact pattern
                 Sign In.dc.html uses: a plain absolutely-positioned text button
                 inside the field that flips the input's type. -->
            <button type="button" id="toggle-password-btn" class="toggle-password" onclick="togglePassword()" aria-pressed="false">${msg("autom.password.toggleShow")}</button>
          </div>
        </div>

        <#-- Keycloak's own stock login.ftl pairs "Remember me" and "Forgot password?"
             on the same row (realm.rememberMe gates the checkbox; usernameHidden is
             never set on this page since username+password share one page here, so
             that half of the condition is always true when rememberMe itself is on).
             realm.rememberMe is currently OFF for this realm (confirmed live via the
             admin API this session) -- see init.py / this task's report for why it
             was left off rather than flipped on directly. When only one of the two
             is present the row collapses to a single flex-end item, matching the
             page's previous single-link layout. -->
        <#if realm.resetPasswordAllowed || (realm.rememberMe && !usernameHidden??)>
        <div class="login-options-row<#if !(realm.rememberMe && !usernameHidden??)> login-options-row--end</#if>">
          <#if realm.rememberMe && !usernameHidden??>
          <label class="remember-me-label">
            <input type="checkbox" id="rememberMe" name="rememberMe" class="remember-me-checkbox" <#if login.rememberMe??>checked</#if> />
            <span>${msg("rememberMe")}</span>
          </label>
          </#if>
          <#if realm.resetPasswordAllowed>
          <a href="${url.loginResetCredentialsUrl}" class="forgot-link">${msg("autom.login.forgotPassword")}</a>
          </#if>
        </div>
        </#if>

        <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>

        <button type="submit" class="btn-primary" name="login">
          ${msg("autom.login.submit")}
        </button>

      </form>

    </div>
      <#include "language-switcher.ftl">
    </div>
  </div>

  <script>
    var pwToggleShowLabel = "${msg("autom.password.toggleShow")?js_string}";
    var pwToggleHideLabel = "${msg("autom.password.toggleHide")?js_string}";
    function togglePassword() {
      var input = document.getElementById('password');
      var btn = document.getElementById('toggle-password-btn');
      var willShow = input.type === 'password';
      input.type = willShow ? 'text' : 'password';
      btn.textContent = willShow ? pwToggleHideLabel : pwToggleShowLabel;
      btn.setAttribute('aria-pressed', willShow ? 'true' : 'false');
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
