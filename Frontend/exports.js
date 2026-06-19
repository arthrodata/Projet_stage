console.log("exports.js loaded");

requireAuth();

const API_URL = "http://127.0.0.1:8001";
const STORAGE_KEY = "biodiversity:last_search_v1";
const HISTORY_KEY = "biodiversity:search_history_v1";
const DEFAULT_RESULT_LIMIT = "300";
const DEFAULT_MAX_EXPORT_PAGES = "20";

const SOURCE_CONFIG = {
    gbif: {
        filename: "resultats.csv",
        source: "GBIF",
        badge: "gbif",
        url: `${API_URL}/search/csv`,
    },
    silene_expert: {
        filename: "resultats_silene_expert.csv",
        source: "Silene Expert",
        badge: "silene",
        url: `${API_URL}/silene-expert/search/csv`,
    },
    both: {
        filename: "resultats_gbif_silene_inaturalist.csv",
        source: "Combined",
        badge: "combined",
        url: `${API_URL}/combined/search/csv`,
    },
    combined: {
        filename: "resultats_gbif_silene_inaturalist.csv",
        source: "Combined",
        badge: "combined",
        url: `${API_URL}/combined/search/csv`,
    },
    inaturalist: {
        filename: "resultats_inaturalist.csv",
        source: "iNaturalist",
        badge: "inaturalist",
        url: `${API_URL}/inaturalist/search/csv`,
    },
    steli: {
        filename: "resultats_steli.csv",
        source: "STELI",
        badge: "steli",
        url: `${API_URL}/steli/search/csv`,
    },
};

function safeParseJson(raw) {
    try {
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function readLocalStorage(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return "";
    }
}

function writeLocalStorage(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch {
        // ignore quota / private mode issues
    }
}

function formatNumber(value) {
    const n = Number(value || 0);
    if (!Number.isFinite(n)) return "0";
    return n.toLocaleString("en-US");
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatSavedDate(value) {
    if (!value) return "Aucun export r\u00e9cent";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Aucun export r\u00e9cent";

    return date.toLocaleString("fr-FR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function getSourceConfig(entry) {
    const source = entry && entry.params && entry.params.source
        ? entry.params.source
        : (entry && entry.source ? entry.source : "gbif");
    return SOURCE_CONFIG[source] || SOURCE_CONFIG.gbif;
}

function getRecordCount(entry) {
    if (entry && Array.isArray(entry.data)) return entry.data.length;
    return entry && Number.isFinite(Number(entry.result_count)) ? Number(entry.result_count) : 0;
}

function getSearchLabel(entry, index) {
    const params = (entry && entry.params) || {};
    const parts = [params.species, params.genus, params.family, params.country]
        .map((value) => String(value || "").trim())
        .filter(Boolean);

    return parts.length > 0 ? parts.join(" / ") : `Recherche ${index + 1}`;
}

function getHistory() {
    const rawHistory = readLocalStorage(HISTORY_KEY);
    const parsedHistory = rawHistory ? safeParseJson(rawHistory) : null;
    const history = Array.isArray(parsedHistory) ? parsedHistory : [];

    if (history.length > 0) return history.slice(0, 10);

    const rawLast = readLocalStorage(STORAGE_KEY);
    const last = rawLast ? safeParseJson(rawLast) : null;
    if (!last || !Array.isArray(last.data)) return [];

    const migrated = [{
        id: last.id || `migrated-${last.savedAt || Date.now()}`,
        savedAt: last.savedAt,
        params: last.params || {},
        data: last.data,
    }];

    writeLocalStorage(HISTORY_KEY, JSON.stringify(migrated));
    return migrated;
}

function historyTimestamp(entry) {
    const date = new Date((entry && (entry.savedAt || entry.created_at)) || 0);
    return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function historyKey(entry) {
    const params = (entry && entry.params) || {};
    return [
        params.source || entry.source || "",
        params.family || "",
        params.genus || "",
        params.species || "",
        params.country || "",
        params.dateFrom || "",
        params.dateTo || "",
        entry && (entry.savedAt || entry.created_at || ""),
    ].join("|");
}

function mergeHistories(serverHistory, localHistory) {
    const seen = new Set();
    return [...(serverHistory || []), ...(localHistory || [])]
        .filter((entry) => entry && typeof entry === "object")
        .sort((a, b) => historyTimestamp(b) - historyTimestamp(a))
        .filter((entry) => {
            const key = historyKey(entry);
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        })
        .slice(0, 10);
}

function buildDownloadUrl(entry) {
    const config = getSourceConfig(entry);
    const params = (entry && entry.params) || {};
    const query = new URLSearchParams();

    if (params.family) query.append("family", params.family);
    if (params.species) query.append("species", params.species);
    if (params.genus) query.append("genus", params.genus);
    if (params.country) query.append("country", params.country);
    if (params.dateFrom) query.append("date_from", params.dateFrom);
    if (params.dateTo) query.append("date_to", params.dateTo);
    query.append("limit", params.resultLimit || DEFAULT_RESULT_LIMIT);
    const maxPages = params.maxPages || DEFAULT_MAX_EXPORT_PAGES;
    if (maxPages && maxPages !== "50") query.append("max_pages", maxPages);
    const source = params.source || (entry && entry.source) || "";
    if ((source === "inaturalist" || source === "both" || source === "combined") && params.qualityGrade) {
        query.append("quality_grade", params.qualityGrade);
    }

    const queryString = query.toString();
    return queryString ? `${config.url}?${queryString}` : config.url;
}

function getCsvColumns(rows) {
    const preferred = [
        "source_bdd",
        "country",
        "coordinates",
        "eventDate",
        "basisOfRecord",
        "datasetName",
        "family",
        "genus",
        "species",
        "quality_grade",
        "status",
        "iucn_status",
        "redListCategory",
    ];
    const keys = new Set();

    rows.forEach((row) => {
        Object.keys(row || {}).forEach((key) => keys.add(key));
    });

    return [
        ...preferred.filter((key) => keys.has(key)),
        ...Array.from(keys).filter((key) => !preferred.includes(key)).sort(),
    ];
}

function csvEscape(value) {
    if (value === undefined || value === null) return "";
    const text = String(value);
    if (/[",\r\n;]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
    return text;
}

function buildCsvFromRows(rows) {
    const safeRows = Array.isArray(rows) ? rows : [];
    const columns = getCsvColumns(safeRows);
    const lines = [
        columns.map(csvEscape).join(","),
        ...safeRows.map((row) => columns.map((column) => csvEscape(row && row[column])).join(",")),
    ];

    return new Blob([`\uFEFF${lines.join("\r\n")}\r\n`], { type: "text/csv;charset=utf-8" });
}

function triggerBlobDownload(blob, filename) {
    const objectUrl = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(objectUrl);
}

function setMessage(text, type) {
    const message = document.getElementById("exportsMessage");
    if (!message) return;

    message.textContent = text;
    message.className = `message-pill ${type || "neutral"}`;
}

function setDownloadLoading(button, isLoading) {
    if (!button) return;
    button.disabled = isLoading;
    button.querySelector(".download-label").textContent = isLoading ? "Pr\u00e9paration..." : "T\u00e9l\u00e9charger";
}

function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return "0 Ko";
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} Ko`;
    return `${(value / (1024 * 1024)).toFixed(1)} Mo`;
}

function formatSeconds(seconds) {
    const value = Math.max(0, Math.round(Number(seconds || 0)));
    if (value < 60) return `${value} s`;
    const minutes = Math.floor(value / 60);
    const rest = value % 60;
    return `${minutes} min ${rest} s`;
}

async function fetchCsvWithProgress(url, filename) {
    const startedAt = Date.now();
    let timer = window.setInterval(() => {
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        setMessage(`Preparation de ${filename}... 0% (${elapsed} s)`, "neutral");
    }, 1000);

    let response;
    try {
        response = await authFetch(url);
    } finally {
        if (timer) {
            window.clearInterval(timer);
            timer = null;
        }
    }

    if (!response.ok) throw new Error(`CSV download failed: ${response.status}`);

    const total = Number(response.headers.get("Content-Length") || 0);
    const contentType = response.headers.get("Content-Type") || "text/csv;charset=utf-8";

    if (!response.body) {
        setMessage(`Telechargement de ${filename}...`, "neutral");
        return response.blob();
    }

    const reader = response.body.getReader();
    const chunks = [];
    let received = 0;
    const downloadStartedAt = Date.now();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;

        if (total > 0) {
            const elapsedSeconds = Math.max(0.1, (Date.now() - downloadStartedAt) / 1000);
            const percent = Math.min(100, Math.round((received / total) * 100));
            const speed = received / elapsedSeconds;
            const remainingSeconds = speed > 0 ? (total - received) / speed : 0;
            setMessage(
                `Telechargement ${filename}: ${percent}% - ${formatBytes(received)} / ${formatBytes(total)} - reste ${formatSeconds(remainingSeconds)}`,
                "neutral"
            );
        } else {
            setMessage(`Telechargement ${filename} en cours - ${formatBytes(received)} recus`, "neutral");
        }
    }

    return new Blob(chunks, { type: contentType });
}

async function downloadCsv(entry, button) {
    const config = getSourceConfig(entry);

    try {
        setDownloadLoading(button, true);
        setMessage(`Pr\u00e9paration de l'export complet ${config.filename}...`, "neutral");

        const blob = await fetchCsvWithProgress(buildDownloadUrl(entry), config.filename);
        triggerBlobDownload(blob, config.filename);

        setMessage(`${config.filename} t\u00e9l\u00e9charg\u00e9.`, "success");
    } catch (error) {
        console.error(error);
        setMessage("Erreur: impossible de t\u00e9l\u00e9charger le CSV.", "error");
    } finally {
        setDownloadLoading(button, false);
    }
}

function renderEmptyState(body) {
    body.innerHTML = `
        <tr>
            <td colspan="6" class="empty-state">Aucun export r\u00e9cent.</td>
        </tr>
    `;
}

async function loadServerHistory() {
    const response = await authFetch(`${API_URL}/history?limit=10`);
    if (!response.ok) throw new Error("History API error");
    return response.json();
}

async function renderExports() {
    const body = document.getElementById("exportsBody");
    if (!body) return;

    let history = [];
    const localHistory = getHistory();
    try {
        history = mergeHistories(await loadServerHistory(), localHistory);
    } catch (error) {
        console.error(error);
        history = localHistory;
    }
    const latest = history[0] || null;
    const latestRecords = getRecordCount(latest);

    document.getElementById("summarySearches").textContent =
        `${formatNumber(history.length)} recherche${history.length > 1 ? "s" : ""}`;
    document.getElementById("summaryRecords").textContent =
        `${formatNumber(latestRecords)} record${latestRecords > 1 ? "s" : ""}`;
    document.getElementById("summaryDate").textContent =
        latest ? formatSavedDate(latest.savedAt) : "Aucun export r\u00e9cent";

    body.innerHTML = "";

    if (history.length === 0) {
        renderEmptyState(body);
        setMessage("Aucun export r\u00e9cent.", "neutral");
        return;
    }

    history.slice(0, 10).forEach((entry, index) => {
        const config = getSourceConfig(entry);
        const recordCount = getRecordCount(entry);
        const searchLabel = escapeHtml(getSearchLabel(entry, index));
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>
                <span class="file-name">${searchLabel}</span>
                <span class="file-path">#${index + 1} dans les 10 derni\u00e8res recherches</span>
            </td>
            <td>
                <span class="file-name">${config.filename}</span>
                <span class="file-path">Backend/exports/${config.filename}</span>
            </td>
            <td><span class="source-badge ${config.badge}">${config.source}</span></td>
            <td class="record-count">${formatNumber(recordCount)} record${recordCount > 1 ? "s" : ""}</td>
            <td class="export-date">${formatSavedDate(entry.savedAt)}</td>
            <td>
                <button type="button" class="download-btn" data-filename="${config.filename}">
                    <span class="download-icon" aria-hidden="true"></span>
                    <span class="download-label">T\u00e9l\u00e9charger</span>
                </button>
            </td>
        `;

        const button = tr.querySelector(".download-btn");
        button.addEventListener("click", () => downloadCsv(entry, button));
        body.appendChild(tr);
    });

    setMessage(`${formatNumber(history.length)} recherche${history.length > 1 ? "s" : ""} dans l'historique.`, "neutral");
}

renderAuthBadge();
renderExports();
