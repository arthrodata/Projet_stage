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
    return n.toLocaleString("fr-FR");
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
    for (const value of values || []) {
        const text = String(value || "").trim();
        const lower = text.toLowerCase();
        if (text !== "" && lower !== "not provided" && lower !== "non renseigne") {
            out.add(text);
        }
    }
    return out;
}

function appendCell(row, value) {
    const td = document.createElement("td");
    td.textContent = value;
    row.appendChild(td);
}

function renderLastRows(rows) {
    const tbody = document.getElementById("lastRowsBody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!Array.isArray(rows) || rows.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 4;
        td.className = "empty-state";
        td.textContent = "Aucune recherche sauvegardee.";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    rows.forEach((item) => {
        const tr = document.createElement("tr");
        appendCell(tr, pick(item, ["source_bdd"]) || "Non renseigne");
        appendCell(tr, pick(item, ["country"]) || "Non renseigne");
        appendCell(tr, pick(item, ["species"]) || "Non renseigne");
        appendCell(tr, pick(item, ["eventDate"]) || "Non renseigne");
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
            if (msg) msg.textContent = "Ouvre la page via http://127.0.0.1:8000 pour lire la derniere recherche.";
        } else if (msg) {
            msg.textContent = "Chargement...";
        }

        const raw = localStorage.getItem(STORAGE_KEY);
        const saved = raw ? safeParseJson(raw) : null;
        const data = saved && Array.isArray(saved.data) ? saved.data : [];

        const connectedSources = 3;
        const csvExports = 4;

        const occurrences = data.length;
        const uniqueSpecies = uniqNonEmpty(data.map((item) => item && item.species)).size;
        const detectedSources = uniqNonEmpty(data.map((item) => item && item.source_bdd)).size;

        setText("statSources", String(connectedSources));
        setText("statExports", String(csvExports));
        setText("statOccurrences", formatNumber(occurrences));
        setText("statSpecies", formatNumber(uniqueSpecies));
        setText(
            "statSourcesMeta",
            occurrences > 0 ? `${formatNumber(detectedSources)} source(s) detectee(s)` : "3 configurees"
        );

        if (!saved || !Array.isArray(saved.data)) {
            if (msg && !(window.location && window.location.protocol === "file:")) {
                msg.textContent = "Aucune recherche sauvegardee.";
            }
            renderLastRows([]);
            return;
        }

        if (msg) msg.textContent = "Derniere recherche chargee";

        renderLastRows(data.slice(-5).reverse());
    } catch (error) {
        console.error(error);
        if (msg) msg.textContent = "Erreur dashboard.";
        renderLastRows([]);
    }
}

initDashboard();
