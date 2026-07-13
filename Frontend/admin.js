const API_URL = window.API_URL;

const usersBody = document.getElementById("usersBody");
const adminMessage = document.getElementById("adminMessage");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");
const deleteUnvalidatedBtn = document.getElementById("deleteUnvalidatedBtn");

function setAdminMessage(text, type) {
    adminMessage.textContent = text;
    adminMessage.className = `message-pill ${type || "neutral"}`;
}

function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("fr-FR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));
}

function renderStatus(user) {
    return user.is_validated
        ? '<span class="status-badge status-badge-valid">Valide</span>'
        : '<span class="status-badge status-badge-pending">Non valide</span>';
}

function renderActions(user, currentUser) {
    if (user.is_admin) {
        return '<span class="muted-text">Administrateur</span>';
    }
    if (currentUser && Number(user.id) === Number(currentUser.id)) {
        return '<span class="muted-text">Compte actuel</span>';
    }

    const validateButton = user.is_validated
        ? `<button type="button" class="btn-muted admin-action" data-action="invalidate" data-user-id="${user.id}">Invalider</button>`
        : `<button type="button" class="btn-primary admin-action" data-action="validate" data-user-id="${user.id}">Valider</button>`;

    return `
        <div class="admin-actions">
            ${validateButton}
            <button type="button" class="btn-danger admin-action" data-action="delete" data-user-id="${user.id}">Supprimer</button>
        </div>
    `;
}

function renderUsers(users) {
    const currentUser = getAuthUser();
    if (!users.length) {
        usersBody.innerHTML = '<tr><td colspan="7" class="empty-state">Aucun utilisateur.</td></tr>';
        return;
    }

    usersBody.innerHTML = users.map((user) => `
        <tr>
            <td>${escapeHtml(user.last_name || "-")}</td>
            <td>${escapeHtml(user.first_name || "-")}</td>
            <td>${escapeHtml(user.email)}</td>
            <td>${renderStatus(user)}</td>
            <td>${user.is_admin ? "Admin" : "Utilisateur"}</td>
            <td>${escapeHtml(formatDate(user.created_at))}</td>
            <td>${renderActions(user, currentUser)}</td>
        </tr>
    `).join("");
}

async function loadUsers() {
    setAdminMessage("Chargement...", "neutral");
    const response = await authFetch(`${API_URL}/admin/users`, { cache: "no-store" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Acces administrateur impossible.");
    }
    renderUsers(payload.users || []);
    setAdminMessage(`${(payload.users || []).length} utilisateur(s)`, "success");
}

async function updateUser(action, userId) {
    let url = `${API_URL}/admin/users/${userId}/${action}`;
    let options = { method: "PATCH" };
    if (action === "delete") {
        const confirmed = window.confirm("Supprimer ce compte utilisateur ?");
        if (!confirmed) return;
        url = `${API_URL}/admin/users/${userId}`;
        options = { method: "DELETE" };
    }

    setAdminMessage("Mise a jour...", "neutral");
    const response = await authFetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Action impossible.");
    }
    await loadUsers();
}

async function runCleanup(kind) {
    const isHistory = kind === "history";
    const confirmed = window.confirm(
        isHistory
            ? "Supprimer tout l'historique des recherches pour tous les utilisateurs ?"
            : "Supprimer tous les comptes non valides ?"
    );
    if (!confirmed) return;

    setAdminMessage("Nettoyage en cours...", "neutral");
    const url = isHistory ? `${API_URL}/admin/history` : `${API_URL}/admin/users/unvalidated`;
    const response = await authFetch(url, { method: "DELETE" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Nettoyage impossible.");
    }
    setAdminMessage(`${payload.deleted || 0} element(s) supprime(s).`, "success");
    if (!isHistory) await loadUsers();
}

usersBody.addEventListener("click", async (event) => {
    const button = event.target.closest(".admin-action");
    if (!button) return;
    try {
        await updateUser(button.dataset.action, button.dataset.userId);
    } catch (error) {
        setAdminMessage(error.message, "error");
    }
});

clearHistoryBtn.addEventListener("click", async () => {
    try {
        await runCleanup("history");
    } catch (error) {
        setAdminMessage(error.message, "error");
    }
});

deleteUnvalidatedBtn.addEventListener("click", async () => {
    try {
        await runCleanup("unvalidated");
    } catch (error) {
        setAdminMessage(error.message, "error");
    }
});

requireAuth();
renderAuthBadge();
loadUsers().catch((error) => {
    setAdminMessage(error.message, "error");
});
