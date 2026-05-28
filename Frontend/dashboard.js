console.log("dashboard.js loaded");

const STORAGE_KEY = "biodiversity:last_search_v1";

function safeParseJson(raw) {
    try {
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function formatNumber(value) {
    const n = Number(value || 0);
    if (!Number.isFinite(n)) return "0";
    return n.toLocaleString("en-US");
}

function pick(item, keys) {
    for (const key of keys) {
        const value = item && item[key];
        if (value !== undefined && value !== null && String(value).trim() !== "") return value;
    }
    return "";
}

function uniqNonEmpty(values) {
    const out = new Set();
    for (const v of values || []) {
        const s = String(v || "").trim();
        const lower = s.toLowerCase();
        if (s !== "" && lower !== "not provided" && lower !== "non renseigne") out.add(s);
    }
    return out;
}

function renderLastRows(rows) {
    const tbody = document.getElementById("lastRowsBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!Array.isArray(rows) || rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No saved search</td></tr>`;
        return;
    }

    rows.forEach((item) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${pick(item, ["source_bdd"]) || "Not provided"}</td>
            <td>${pick(item, ["country"]) || "Not provided"}</td>
            <td>${pick(item, ["species"]) || "Not provided"}</td>
            <td>${pick(item, ["eventDate"]) || "Not provided"}</td>
        `;
        tbody.appendChild(tr);
    });
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function initDashboard() {
    const msg = document.getElementById("dashMessage");
    try {
        if (window.location && window.location.protocol === "file:") {
            if (msg) msg.textContent = "Open via a local server (http://...) to access saved searches.";
        } else if (msg) {
            msg.textContent = "Loading...";
        }

        const raw = localStorage.getItem(STORAGE_KEY);
        const saved = raw ? safeParseJson(raw) : null;
        const data = saved && Array.isArray(saved.data) ? saved.data : [];

        // Defaults if no saved search
        const connectedSources = 3;
        const csvExports = 3;

        const occurrences = Array.isArray(data) ? data.length : 0;
        const uniqueSpecies = uniqNonEmpty((data || []).map((it) => it && it.species)).size;
        const detectedSources = uniqNonEmpty((data || []).map((it) => it && it.source_bdd)).size;

        setText("statSources", String(connectedSources));
        setText("statExports", String(csvExports));
        setText("statOccurrences", formatNumber(occurrences));
        setText("statSpecies", formatNumber(uniqueSpecies));

        setText(
            "statSourcesMeta",
            occurrences > 0 ? `${formatNumber(detectedSources)} source(s) detected` : "3 configured"
        );

        if (!saved || !Array.isArray(saved.data)) {
            if (msg && !(window.location && window.location.protocol === "file:")) msg.textContent = "No saved search.";
            renderLastRows([]);
            return;
        }

        if (msg) msg.textContent = "Last search loaded";

        const lastFive = data.slice(-5).reverse();
        renderLastRows(lastFive);
    } catch (error) {
        console.error(error);
        if (msg) msg.textContent = "Dashboard error (check console).";
        renderLastRows([]);
    }
}

initDashboard();
