const API_URL = "http://127.0.0.1:8000";

const form = document.getElementById("authForm");
const firstNameInput = document.getElementById("firstName");
const lastNameInput = document.getElementById("lastName");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const registerBtn = document.getElementById("registerBtn");
const authMessage = document.getElementById("authMessage");

function setAuthMessage(text, type) {
    authMessage.textContent = text;
    authMessage.className = `message-pill ${type || "neutral"}`;
}

function nextUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("next") || "dashboard.html";
}

async function submitAuth(mode) {
    const firstName = firstNameInput.value.trim();
    const lastName = lastNameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !password) {
        setAuthMessage("Email et mot de passe requis.", "error");
        return;
    }
    if (mode === "register" && (!firstName || !lastName)) {
        setAuthMessage("Prenom et nom requis pour creer un compte.", "error");
        return;
    }

    setAuthMessage(mode === "register" ? "Creation du compte..." : "Connexion...", "neutral");
    const response = await fetch(`${API_URL}/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, first_name: firstName, last_name: lastName }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Erreur authentification.");
    }
    setAuthSession(payload);
    window.location.href = nextUrl();
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await submitAuth("login");
    } catch (error) {
        setAuthMessage(error.message, "error");
    }
});

registerBtn.addEventListener("click", async () => {
    try {
        await submitAuth("register");
    } catch (error) {
        setAuthMessage(error.message, "error");
    }
});
