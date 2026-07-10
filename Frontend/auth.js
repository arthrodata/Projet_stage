const AUTH_TOKEN_KEY = "biodiversity:auth_token";
const AUTH_USER_KEY = "biodiversity:auth_user";

function clearLegacyPersistentAuth() {
    try {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_USER_KEY);
    } catch {
        // ignore storage errors
    }
}

function getAuthToken() {
    try {
        clearLegacyPersistentAuth();
        return sessionStorage.getItem(AUTH_TOKEN_KEY) || "";
    } catch {
        return "";
    }
}

function getAuthUser() {
    try {
        clearLegacyPersistentAuth();
        const raw = sessionStorage.getItem(AUTH_USER_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

function getAuthStorageKey(baseKey) {
    const user = getAuthUser();
    const userKey = user && user.id ? `user:${user.id}` : "anonymous";
    return `${baseKey}:${userKey}`;
}

function setAuthSession(payload) {
    if (!payload || !payload.access_token) return;
    clearLegacyPersistentAuth();
    sessionStorage.setItem(AUTH_TOKEN_KEY, payload.access_token);
    sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(payload.user || {}));
}

function clearAuthSession() {
    try {
        sessionStorage.removeItem(AUTH_TOKEN_KEY);
        sessionStorage.removeItem(AUTH_USER_KEY);
        clearLegacyPersistentAuth();
    } catch {
        // ignore storage errors
    }
}

function authHeaders(extraHeaders) {
    const headers = { ...(extraHeaders || {}) };
    const token = getAuthToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
}

async function authFetch(url, options) {
    const opts = options || {};
    const response = await fetch(url, {
        ...opts,
        headers: authHeaders(opts.headers),
    });
    if (response.status === 401) {
        clearAuthSession();
        const next = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
        window.location.href = `login.html?next=${next}`;
    }
    if (response.status === 403) {
        const clone = response.clone();
        const payload = await clone.json().catch(() => ({}));
        const detail = String(payload.detail || "");
        if (detail.includes("attente de validation")) {
            clearAuthSession();
            window.location.href = "login.html";
        }
    }
    return response;
}

function requireAuth() {
    if (getAuthToken()) return;
    const next = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);
    window.location.href = `login.html?next=${next}`;
}

function logout() {
    clearAuthSession();
    window.location.href = "login.html";
}

function renderAdminNavLink() {
    const user = getAuthUser();
    const navs = document.querySelectorAll(".side-nav");
    navs.forEach((nav) => {
        const existing = nav.querySelector('[data-admin-link="true"]');
        if (existing) existing.remove();
        if (!user || !user.is_admin) return;

        const link = document.createElement("a");
        link.className = `nav-item ${window.location.pathname.endsWith("admin.html") ? "active" : ""}`;
        link.href = "admin.html";
        link.dataset.adminLink = "true";
        link.innerHTML = `
            <span class="nav-icon">AD</span>
            Admin
        `;
        nav.appendChild(link);
    });
}

function renderAuthBadge() {
    const sidebars = document.querySelectorAll(".sidebar");
    if (!sidebars.length) return;
    const user = getAuthUser();
    const displayName = user && user.display_name ? user.display_name : "";
    const fallbackName = user && (user.first_name || user.last_name)
        ? `${user.first_name || ""} ${user.last_name || ""}`.trim()
        : "";
    const label = displayName || fallbackName || "Signed-in user";
    sidebars.forEach((sidebar) => {
        const existing = sidebar.querySelector(".auth-card");
        if (existing) existing.remove();

        const authCard = document.createElement("div");
        authCard.className = "api-card auth-card";
        authCard.innerHTML = `
            <div class="auth-card-main">
                <span class="status-dot"></span>
                <div>
                    <strong>${label}</strong>
                    <p>Personal workspace</p>
                </div>
            </div>
            <button type="button" class="auth-logout">Logout</button>
        `;
        const button = authCard.querySelector(".auth-logout");
        button.addEventListener("click", logout);
        sidebar.appendChild(authCard);
    });
    renderAdminNavLink();
}
