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
                <h1 class="title">Sign in</h1>
                <p class="subtitle">Autom Super Admin is an internal surface. Sign in with your Autom staff account.</p>
            </div>

            <#if messagesPerField.existsError('username')>
            <div class="error-banner" role="alert">
                ${messagesPerField.getFirstError('username')}
            </div>
            </#if>

            <form id="kc-form-login" action="${url.loginAction}" method="post">

                <div class="field">
                    <label for="username" class="label">Work email</label>
                    <input
                        type="text"
                        id="username"
                        name="username"
                        value="${(login.username!'')}"
                        autocomplete="username"
                        class="input<#if messagesPerField.existsError('username')> input--error</#if>"
                        autofocus
                    />
                </div>

                <button type="submit" class="btn-primary">Continue</button>

            </form>
        </div>
    </div>
</body>
</html>
