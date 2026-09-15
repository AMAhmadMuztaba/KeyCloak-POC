<#-- Included at the bottom of every custom page's .card. Zero-JS: a <details>
     element toggles the dropdown, and picking a language is a normal link
     navigation (full page reload with ?kc_locale=xx, set by Keycloak itself
     via locale.supported[].url), so there's no open/close state to manage. -->
<#if realm.internationalizationEnabled && locale.supported?size gt 1>
    <div class="lang-switcher">
        <details class="lang-switcher-details">
            <summary class="lang-switcher-trigger" aria-label="${msg("autom.language.label")}">
                <svg class="lang-switcher-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="2" y1="12" x2="22" y2="12"/>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                </svg>
                <span>${locale.current}</span>
            </summary>
            <ul class="lang-switcher-menu" role="menu">
                <#list locale.supported as l>
                    <li role="none"><a role="menuitem" href="${l.url}" class="lang-switcher-item">${l.label}</a></li>
                </#list>
            </ul>
        </details>
    </div>
</#if>
