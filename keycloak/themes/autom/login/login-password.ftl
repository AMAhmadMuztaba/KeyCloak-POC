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
                <h1 class="title">Sign in</h1>
                <p class="subtitle">Autom Super Admin is an internal surface. Sign in with your Autom staff account.</p>
            </div>

            <#if messagesPerField.existsError('password')>
            <div class="error-banner" role="alert">
                ${messagesPerField.getFirstError('password')}
            </div>
            </#if>

            <form id="kc-form-login" action="${url.loginAction}" method="post">

                <div class="field">
                    <label for="password" class="label">Password</label>
                    <input
                        type="password"
                        id="password"
                        name="password"
                        autocomplete="current-password"
                        class="input<#if messagesPerField.existsError('password')> input--error</#if>"
                        autofocus
                    />
                </div>

                <#if realm.resetPasswordAllowed>
                <div style="text-align: right; margin-top: -0.5rem; margin-bottom: 1rem;">
                    <a href="${url.loginResetCredentialsUrl}" class="forgot-link">Forgot password?</a>
                </div>
                </#if>

                <button type="submit" class="btn-primary">Sign in</button>

            </form>
        </div>
        </div>
    </div>
</body>
</html>
