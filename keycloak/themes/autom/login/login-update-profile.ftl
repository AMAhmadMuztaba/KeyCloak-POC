<#import "template.ftl" as layout>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Your details — Autom</title>
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
            </div>

            <div class="step-progress" role="group" aria-label="${msg("autom.profile.eyebrow")}">
                <span class="is-current"></span>
                <span></span>
                <span></span>
            </div>

            <div class="header">
                <p class="eyebrow">${msg("autom.profile.eyebrow")}</p>
                <h1 class="title">${msg("autom.profile.title")}</h1>
                <p class="subtitle">${msg("autom.profile.subtitle")}</p>
            </div>

            <#if message?has_content>
            <div class="alert alert-${message.type}">
                ${kcSanitize(message.summary)?no_esc}
            </div>
            </#if>

            <form id="kc-update-profile-form" action="${url.loginAction}" method="post">

                <div class="avatar-row">
                    <div class="avatar-circle" id="avatar-circle">
                        <span id="avatar-initials">?</span>
                        <img id="avatar-preview" alt="" style="display:none;">
                    </div>
                    <div class="avatar-upload">
                        <button type="button" class="btn-secondary btn-avatar" id="avatar-pick-btn">${msg("autom.profile.addPicture")}</button>
                        <p class="avatar-caption">${msg("autom.profile.pictureCaption")}</p>
                        <p class="avatar-error" id="avatar-error" style="display:none;"></p>
                    </div>
                    <#-- Not submitted itself (no name) -- its contents are read client-side and
                         stashed into the hidden profilePictureDataUrl field below instead. A
                         multipart form (needed for a real file field) breaks Keycloak's stock
                         UpdateProfile.processAction() on this server version -- it also calls
                         getDecodedFormParameters(), which throws once any file part is present
                         (confirmed live via a container stack trace) -- so the picture travels
                         as a base64 data URL in an ordinary url-encoded field instead, the same
                         mechanism already proven to work for every other field on this form. -->
                    <input type="file" id="avatar-file-input" accept="image/png,image/jpeg,image/webp" style="display:none;">
                    <input type="hidden" id="profilePictureDataUrl" name="profilePictureDataUrl" value="">
                </div>

                <#list profile.attributes as attribute>
                    <#if attribute.name == 'firstName'>
                        <div class="field">
                            <label for="firstName" class="label">${msg("autom.profile.firstNameLabel")}</label>
                            <input
                                type="text" id="firstName" name="firstName"
                                value="${(attribute.value!'')}"
                                class="input<#if messagesPerField.existsError('firstName')> input--error</#if>"
                                autocomplete="given-name"
                                autofocus
                            />
                            <#if messagesPerField.existsError('firstName')>
                                <span class="field-error">${kcSanitize(messagesPerField.get('firstName'))?no_esc}</span>
                            </#if>
                        </div>
                    <#elseif attribute.name == 'lastName'>
                        <div class="field">
                            <label for="lastName" class="label">${msg("autom.profile.lastNameLabel")}</label>
                            <input
                                type="text" id="lastName" name="lastName"
                                value="${(attribute.value!'')}"
                                class="input<#if messagesPerField.existsError('lastName')> input--error</#if>"
                                autocomplete="family-name"
                            />
                            <#if messagesPerField.existsError('lastName')>
                                <span class="field-error">${kcSanitize(messagesPerField.get('lastName'))?no_esc}</span>
                            </#if>
                        </div>
                    <#elseif attribute.name == 'email'>
                        <div class="info-box">
                            <div class="info-box-row">
                                <span class="info-box-label">${msg("autom.profile.emailLabel")}</span>
                                <span class="info-box-value">${(attribute.value!'')}</span>
                                <span class="info-box-caption">${msg("autom.profile.emailCaption")}</span>
                            </div>
                            <#if automJoiningOrgName??>
                            <div class="info-box-row">
                                <span class="info-box-label">${msg("autom.profile.joiningLabel")}</span>
                                <span class="info-box-value">${automJoiningOrgName}<#if automJoiningRole??> · ${automJoiningRole}</#if></span>
                            </div>
                            </#if>
                        </div>
                        <input type="hidden" name="email" value="${(attribute.value!'')}" />
                    <#elseif attribute.name == 'username'>
                        <input type="hidden" name="username" value="${(attribute.value!'')}" />
                    </#if>
                </#list>

                <button type="submit" class="btn-primary">${msg("autom.profile.continue")}</button>

            </form>

            <#include "language-switcher.ftl">
        </div>
    </div>

    <script>
        (function () {
            var MAX_BYTES = 2 * 1024 * 1024;
            var ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
            var ERROR_TYPE = "${msg("autom.profile.pictureErrorType")?js_string}";
            var ERROR_SIZE = "${msg("autom.profile.pictureErrorSize")?js_string}";

            var firstNameField = document.getElementById('firstName');
            var lastNameField = document.getElementById('lastName');
            var initialsEl = document.getElementById('avatar-initials');
            var previewEl = document.getElementById('avatar-preview');
            var pickBtn = document.getElementById('avatar-pick-btn');
            var fileInput = document.getElementById('avatar-file-input');
            var dataUrlField = document.getElementById('profilePictureDataUrl');
            var errorEl = document.getElementById('avatar-error');

            function updateInitials() {
                var first = (firstNameField && firstNameField.value || '').trim();
                var last = (lastNameField && lastNameField.value || '').trim();
                var initials = ((first[0] || '') + (last[0] || '')).toUpperCase();
                initialsEl.textContent = initials || '?';
            }

            if (firstNameField) firstNameField.addEventListener('input', updateInitials);
            if (lastNameField) lastNameField.addEventListener('input', updateInitials);
            updateInitials();

            function showError(message) {
                errorEl.textContent = message;
                errorEl.style.display = message ? 'block' : 'none';
            }

            pickBtn.addEventListener('click', function () {
                fileInput.click();
            });

            fileInput.addEventListener('change', function () {
                var file = fileInput.files && fileInput.files[0];
                if (!file) return;

                if (ALLOWED_TYPES.indexOf(file.type) === -1) {
                    showError(ERROR_TYPE);
                    fileInput.value = '';
                    return;
                }
                if (file.size > MAX_BYTES) {
                    showError(ERROR_SIZE);
                    fileInput.value = '';
                    return;
                }

                showError('');

                var reader = new FileReader();
                reader.onload = function (e) {
                    dataUrlField.value = e.target.result;
                    previewEl.src = e.target.result;
                    previewEl.style.display = 'block';
                    initialsEl.style.display = 'none';
                };
                reader.readAsDataURL(file);
            });
        })();
    </script>
</body>
</html>
