<#import "template.ftl" as layout>
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login</title>
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

    <form id="kc-form-login" action="${url.loginAction}" method="post">

      <div class="kc-form-group">
        <label for="username">Email</label>
        <input
          id="username"
          name="username"
          type="text"
          value="${(login.username!'')}"
          autocomplete="username"
          placeholder="Enter your email"
          autofocus
        />
      </div>

      <div class="kc-form-group">
        <label for="password">Password</label>
        <div class="password-wrap">
          <input
            id="password"
            name="password"
            type="password"
            autocomplete="current-password"
            placeholder="Enter your password"
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
        <div class="forgot-password-row">
          <a href="${url.loginResetCredentialsUrl}">Forgot password?</a>
        </div>
      </#if>

      <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>

      <button type="submit" class="kc-login-btn" name="login">
        Log in
      </button>

    </form>
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
  </script>
</body>
</html>
