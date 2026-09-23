<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Set a password — Autom</title>
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

            <div class="step-progress" role="group" aria-label="${msg("autom.password.eyebrow")}">
                <span class="is-done"></span>
                <span class="is-current"></span>
                <span></span>
            </div>

            <div class="header">
                <p class="eyebrow">${msg("autom.password.eyebrow")}</p>
                <h1 class="title">${msg("autom.password.title")}</h1>
            </div>

            <#if messagesPerField.existsError('password-new','password-confirm')>
            <div class="error-banner" role="alert">
                ${messagesPerField.getFirstError('password-new','password-confirm')}
            </div>
            </#if>

            <form action="${url.loginAction}" method="post" id="kc-passwd-update-form">

                <input type="text" name="username" value="${username!''}" autocomplete="username" style="display:none">

                <div class="field">
                    <label for="password-new" class="label">${msg("autom.password.fieldLabel")}</label>
                    <div class="password-wrap">
                        <input
                            type="password"
                            id="password-new"
                            name="password-new"
                            autocomplete="new-password"
                            class="input<#if messagesPerField.existsError('password-new')> input--error</#if>"
                            autofocus
                        />
                        <button type="button" class="toggle-password" id="pw-toggle">${msg("autom.password.toggleShow")}</button>
                    </div>
                </div>

                <div class="field">
                    <label for="password-confirm" class="label">${msg("autom.password.confirmLabel")}</label>
                    <input
                        type="password"
                        id="password-confirm"
                        name="password-confirm"
                        autocomplete="new-password"
                        class="input<#if messagesPerField.existsError('password-confirm')> input--error</#if>"
                    />
                </div>

                <#-- Mirrors the realm's actual password policy (length(12) and
                     upperCase(1) and lowerCase(1) and digits(1)) -- these rules
                     must stay in sync with that policy, or this checklist can
                     show all-green for a password Keycloak's own server-side
                     validation then rejects, which just looks like the page is
                     stuck/looping with no visible reason why. -->
                <ul class="pw-rules" aria-label="${msg("autom.password.title")}">
                    <li class="pw-rule" id="pw-rule-length" data-met="false">
                        <span class="pw-rule-mark" aria-hidden="true">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 4"/></svg>
                        </span>
                        <span>${msg("autom.password.rule.length")}</span>
                    </li>
                    <li class="pw-rule" id="pw-rule-upper" data-met="false">
                        <span class="pw-rule-mark" aria-hidden="true">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 4"/></svg>
                        </span>
                        <span>${msg("autom.password.rule.upper")}</span>
                    </li>
                    <li class="pw-rule" id="pw-rule-lower" data-met="false">
                        <span class="pw-rule-mark" aria-hidden="true">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 4"/></svg>
                        </span>
                        <span>${msg("autom.password.rule.lower")}</span>
                    </li>
                    <li class="pw-rule" id="pw-rule-digit" data-met="false">
                        <span class="pw-rule-mark" aria-hidden="true">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 4"/></svg>
                        </span>
                        <span>${msg("autom.password.rule.digit")}</span>
                    </li>
                    <li class="pw-rule" id="pw-rule-breach" data-met="false">
                        <span class="pw-rule-mark" aria-hidden="true">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 4"/></svg>
                        </span>
                        <span>${msg("autom.password.rule.breach")}</span>
                    </li>
                    <li class="pw-rule" id="pw-rule-match" data-met="false">
                        <span class="pw-rule-mark" aria-hidden="true">
                            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 8.5 6.5 12 13 4"/></svg>
                        </span>
                        <span>${msg("autom.password.rule.match")}</span>
                    </li>
                </ul>

                <#if isAppInitiatedAction??>
                <div style="display:flex; gap:0.5rem; margin-top: 1.25rem;">
                    <button type="submit" class="btn-primary" style="flex:1;" name="login-actions-next-button" value="${action}">
                        ${msg("autom.password.continue")}
                    </button>
                    <button type="submit" class="btn-secondary" name="cancel-aia" value="true">
                        ${msg("doCancel")}
                    </button>
                </div>
                <#else>
                <button type="submit" class="btn-primary" style="margin-top: 1.25rem;">
                    ${msg("autom.password.continue")}
                </button>
                </#if>

            </form>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>

    <script>
        (function () {
            var SHOW_LABEL = "${msg("autom.password.toggleShow")?js_string}";
            var HIDE_LABEL = "${msg("autom.password.toggleHide")?js_string}";
            var BREACHED = ['password', '123456', 'qwerty', 'letmein', 'autom', 'welcome'];
            var pwField = document.getElementById('password-new');
            var confirmField = document.getElementById('password-confirm');
            var toggle = document.getElementById('pw-toggle');
            var ruleLength = document.getElementById('pw-rule-length');
            var ruleUpper = document.getElementById('pw-rule-upper');
            var ruleLower = document.getElementById('pw-rule-lower');
            var ruleDigit = document.getElementById('pw-rule-digit');
            var ruleBreach = document.getElementById('pw-rule-breach');
            var ruleMatch = document.getElementById('pw-rule-match');

            function setMet(el, met) {
                el.setAttribute('data-met', met ? 'true' : 'false');
            }

            function evaluate() {
                var pw = pwField.value;
                var low = pw.toLowerCase();
                setMet(ruleLength, pw.length >= 12);
                setMet(ruleUpper, /[A-Z]/.test(pw));
                setMet(ruleLower, /[a-z]/.test(pw));
                setMet(ruleDigit, /[0-9]/.test(pw));
                setMet(ruleBreach, pw.length > 0 && BREACHED.every(function (b) { return low.indexOf(b) === -1; }));
                setMet(ruleMatch, pw.length > 0 && pw === confirmField.value);
            }

            pwField.addEventListener('input', evaluate);
            confirmField.addEventListener('input', evaluate);

            toggle.addEventListener('click', function () {
                var shown = pwField.type === 'text';
                pwField.type = shown ? 'password' : 'text';
                confirmField.type = shown ? 'password' : 'text';
                toggle.textContent = shown ? SHOW_LABEL : HIDE_LABEL;
            });
        })();
    </script>
</body>
</html>
