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
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/cropperjs@1.6.2/dist/cropper.min.css">
    <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
    <div class="page">
        <img src="${url.resourcesPath}/img/logo-lockup.svg" alt="Autom" class="page-logo">
        <div class="card-col">
        <div class="card">

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

            <#-- Keycloak sets an INFO/WARNING-level message on this required action's
                 very first render ("You need to update your user profile to activate
                 your account.") purely to explain why the page appeared -- redundant
                 here since the header/subtitle already do that. Only a real
                 validation failure (type "error", e.g. a required field left empty
                 after Continue) should surface as an alert. -->
            <#if message?has_content && message.type == 'error'>
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
                    <#-- Not submitted itself (no name) -- its contents are read client-side,
                         cropped, and stashed into the hidden profilePictureDataUrl field below
                         instead. A multipart form (needed for a real file field) breaks
                         Keycloak's stock UpdateProfile.processAction() on this server version --
                         it also calls getDecodedFormParameters(), which throws once any file
                         part is present (confirmed live via a container stack trace) -- so the
                         picture travels as a base64 data URL in an ordinary url-encoded field
                         instead, the same mechanism already proven to work for every other field
                         on this form. -->
                    <input type="file" id="avatar-file-input" accept="image/png,image/jpeg,image/webp" style="display:none;">
                    <input type="hidden" id="profilePictureDataUrl" name="profilePictureDataUrl" value="">
                </div>

                <div class="crop-overlay" id="crop-overlay" style="display:none;">
                    <div class="crop-modal">
                        <p class="crop-modal-title">${msg("autom.profile.cropTitle")}</p>
                        <div class="crop-canvas-wrap">
                            <img id="crop-image" alt="">
                        </div>
                        <div class="crop-zoom-row">
                            <input type="range" id="crop-zoom" min="0" max="1" step="0.01" value="0">
                        </div>
                        <div class="crop-modal-actions">
                            <button type="button" class="btn-secondary" id="crop-cancel-btn">${msg("autom.profile.cropCancel")}</button>
                            <button type="button" class="btn-primary" id="crop-save-btn">${msg("autom.profile.cropSave")}</button>
                        </div>
                    </div>
                </div>

                <#-- First/last name sit side by side (Onboarding.dc.html's
                     grid-template-columns: repeat(2, ...)) -- two separate
                     name-filtered passes over profile.attributes, both inside
                     one grid wrapper, since Keycloak's own list can't be
                     re-ordered or peeked ahead to pair them in a single pass. -->
                <div class="field-grid-2">
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
                        </#if>
                    </#list>
                    <#list profile.attributes as attribute>
                        <#if attribute.name == 'lastName'>
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
                        </#if>
                    </#list>
                </div>

                <#list profile.attributes as attribute>
                    <#if attribute.name == 'firstName' || attribute.name == 'lastName'>
                        <#-- already rendered above -->
                    <#elseif attribute.name == 'email'>
                        <div class="field">
                            <label class="label">${msg("autom.profile.emailLabel")}</label>
                            <div class="input input--static">${(attribute.value!'')}</div>
                        </div>
                        <input type="hidden" name="email" value="${(attribute.value!'')}" />
                    <#elseif attribute.name == 'username'>
                        <input type="hidden" name="username" value="${(attribute.value!'')}" />
                    </#if>
                </#list>

                <button type="submit" class="btn-primary">${msg("autom.profile.continue")}</button>

            </form>

        </div>
            <#include "language-switcher.ftl">
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/cropperjs@1.6.2/dist/cropper.min.js"></script>
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

            var cropOverlay = document.getElementById('crop-overlay');
            var cropImage = document.getElementById('crop-image');
            var cropZoom = document.getElementById('crop-zoom');
            var cropCancelBtn = document.getElementById('crop-cancel-btn');
            var cropSaveBtn = document.getElementById('crop-save-btn');
            var cropper = null;

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

            function closeCropModal() {
                cropOverlay.style.display = 'none';
                if (cropper) {
                    cropper.destroy();
                    cropper = null;
                }
                cropImage.src = '';
                fileInput.value = '';
            }

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
                    cropImage.src = e.target.result;
                    cropOverlay.style.display = 'flex';
                    cropZoom.value = 0;
                    cropper = new Cropper(cropImage, {
                        aspectRatio: 1,
                        viewMode: 1,
                        dragMode: 'move',
                        autoCropArea: 1,
                        background: false,
                        zoomOnWheel: false
                    });
                };
                reader.readAsDataURL(file);
            });

            cropZoom.addEventListener('input', function () {
                if (!cropper) return;
                cropper.zoomTo(1 + parseFloat(cropZoom.value || '0'));
            });

            cropCancelBtn.addEventListener('click', closeCropModal);

            cropSaveBtn.addEventListener('click', function () {
                if (!cropper) return;
                var canvas = cropper.getCroppedCanvas({
                    width: 400,
                    height: 400,
                    imageSmoothingQuality: 'high'
                });
                if (!canvas) { closeCropModal(); return; }

                var dataUrl = canvas.toDataURL('image/jpeg', 0.92);
                dataUrlField.value = dataUrl;
                previewEl.src = dataUrl;
                previewEl.style.display = 'block';
                initialsEl.style.display = 'none';
                closeCropModal();
            });
        })();
    </script>
</body>
</html>
