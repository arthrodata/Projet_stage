const API_URL = window.API_URL;

const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const loginEmailInput = document.getElementById("loginEmail");
const loginPasswordInput = document.getElementById("loginPassword");
const signupFirstNameInput = document.getElementById("signupFirstName");
const signupLastNameInput = document.getElementById("signupLastName");
const signupEmailInput = document.getElementById("signupEmail");
const signupPasswordInput = document.getElementById("signupPassword");
const loginModeBtn = document.getElementById("loginModeBtn");
const signupModeBtn = document.getElementById("signupModeBtn");
const authMessage = document.getElementById("authMessage");
const forgotPasswordBtn = document.getElementById("forgotPasswordBtn");
const forgotPasswordPanel = document.getElementById("forgotPasswordPanel");

function setAuthMessage(text, type) {
    authMessage.textContent = text;
    authMessage.className = `message-pill ${type || "neutral"}`;
}

function nextUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("next") || "dashboard.html";
}

function setAuthMode(mode) {
    const isSignup = mode === "register";
    loginForm.hidden = isSignup;
    signupForm.hidden = !isSignup;
    forgotPasswordPanel.hidden = true;
    loginModeBtn.classList.toggle("active", !isSignup);
    signupModeBtn.classList.toggle("active", isSignup);
    setAuthMessage(isSignup ? "Create your account." : "Sign in with your email and password.", "neutral");
}

async function submitLogin() {
    const email = loginEmailInput.value.trim();
    const password = loginPasswordInput.value;
    if (!email || !password) {
        setAuthMessage("Email and password are required.", "error");
        return;
    }

    setAuthMessage("Signing in...", "neutral");
    const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Authentication error.");
    }
    setAuthSession(payload);
    window.location.href = nextUrl();
}

async function submitSignup() {
    const firstName = signupFirstNameInput.value.trim();
    const lastName = signupLastNameInput.value.trim();
    const email = signupEmailInput.value.trim();
    const password = signupPasswordInput.value;
    if (!email || !password) {
        setAuthMessage("Email and password are required.", "error");
        return;
    }
    if (!firstName || !lastName) {
        setAuthMessage("First name and last name are required to create an account.", "error");
        return;
    }

    setAuthMessage("Creating account...", "neutral");
    const response = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, first_name: firstName, last_name: lastName }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Authentication error.");
    }
    if (payload.status === "pending_validation") {
        signupForm.reset();
        setAuthMode("login");
        setAuthMessage(payload.message || "Account created. Waiting for administrator validation.", "success");
        return;
    }
    setAuthSession(payload);
    window.location.href = nextUrl();
}

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await submitLogin();
    } catch (error) {
        setAuthMessage(error.message, "error");
    }
});

signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await submitSignup();
    } catch (error) {
        setAuthMessage(error.message, "error");
    }
});

loginModeBtn.addEventListener("click", () => setAuthMode("login"));
signupModeBtn.addEventListener("click", () => setAuthMode("register"));
forgotPasswordBtn.addEventListener("click", () => {
    forgotPasswordPanel.hidden = !forgotPasswordPanel.hidden;
    if (!forgotPasswordPanel.hidden) {
        setAuthMessage("Ask an administrator for a temporary password.", "neutral");
    }
});

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) return;
        const shouldShow = input.type === "password";
        input.type = shouldShow ? "text" : "password";
        button.textContent = shouldShow ? "Hide" : "Show";
        button.setAttribute("aria-label", shouldShow ? "Hide password" : "Show password");
    });
});

setAuthMode("login");
