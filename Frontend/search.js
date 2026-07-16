console.log("search.js loaded");

requireAuth();

const API_URL = window.API_URL;
const STORAGE_KEY = getAuthStorageKey("biodiversity:last_search_v1");
const LAST_RESULTS_KEY = getAuthStorageKey("biodiversity_last_results");
const HISTORY_KEY = getAuthStorageKey("biodiversity:search_history_v1");
const DEFAULT_RESULT_LIMIT = "300";
const DEFAULT_EXPORT_PAGE_LIMIT = "300";
const DEFAULT_MAX_EXPORT_PAGES = "34";
const STORED_RESULTS_LIMIT = 1000;
const SEARCH_TIMEOUT_MS = 45000;

const searchBtn = document.getElementById("searchBtn");
const resetBtn = document.getElementById("resetBtn");
const exportBtn = document.getElementById("exportBtn");

const resultsBody = document.getElementById("resultsBody");
const countText = document.getElementById("countText");
const message = document.getElementById("message");
const downloadProgress = document.getElementById("downloadProgress");
const downloadProgressText = document.getElementById("downloadProgressText");
const downloadProgressValue = document.getElementById("downloadProgressValue");
const downloadProgressBar = document.getElementById("downloadProgressBar");
const citationBox = document.getElementById("citationBox");
const copyCitationBtn = document.getElementById("copyCitationBtn");
const citationFeedback = document.getElementById("citationFeedback");

const sourceSelect = document.getElementById("sourceSelect");
const sourceCards = document.querySelectorAll(".source-card");

const familyInput = document.getElementById("family");
const speciesInput = document.getElementById("species");
const genusInput = document.getElementById("genus");
const countryInput = document.getElementById("country");
const dateFromInput = document.getElementById("dateFrom");
const dateToInput = document.getElementById("dateTo");
const qualityGradeInput = document.getElementById("qualityGrade");
const sourceHint = document.getElementById("sourceHint");
const SOURCE_LABELS = {
    gbif: "GBIF",
    silene_expert: "Silene Expert",
    inaturalist: "iNaturalist",
    steli: "STELI",
};
let activeSource = "gbif";
let searchRunId = 0;
let searchAbortController = null;
let currentCitationText = "";

function formatNumber(value) {
    const n = Number(value || 0);
    if (!Number.isFinite(n)) return "0";
    return n.toLocaleString("en-US");
}

function normalizeSource(value) {
    const source = String(value || "").trim();
    if (source === "combined") return "both";
    if (["gbif", "silene_expert", "inaturalist", "steli", "both"].includes(source)) return source;
    return "gbif";
}

function setActiveSource(source) {
    activeSource = normalizeSource(source);
    if (sourceSelect) sourceSelect.value = activeSource;
    syncSourceCards();
}

function handleSourceChange(source) {
    setActiveSource(source);
    setMessage("Source selected. Click Run analysis to search.", "neutral");
}

function removeLegacySearchWidget() {
    const legacyInput = document.querySelector('input[placeholder^="Search species"]');
    if (!legacyInput) return;

    const legacyContainer = legacyInput.closest("form, section, header, div");
    if (legacyContainer && legacyContainer !== document.body && !legacyContainer.classList.contains("field")) {
        legacyContainer.remove();
        return;
    }

    legacyInput.remove();
}

function setLoading(isLoading) {
    searchBtn.disabled = isLoading;
    resetBtn.disabled = isLoading;
    exportBtn.disabled = isLoading;
    sourceCards.forEach((card) => {
        card.disabled = isLoading;
    });
}

function getQueryParams() {
    const source = normalizeSource(activeSource || (sourceSelect && sourceSelect.value));
    const family = familyInput.value.trim();
    const species = speciesInput.value.trim();
    const genus = genusInput.value.trim();
    const country = countryInput.value.trim();
    const dateFrom = (dateFromInput && dateFromInput.value ? dateFromInput.value : "").trim();
    const dateTo = (dateToInput && dateToInput.value ? dateToInput.value : "").trim();
    const qualityGrade = (qualityGradeInput && qualityGradeInput.value ? qualityGradeInput.value : "").trim();
    const resultLimit = DEFAULT_RESULT_LIMIT;
    const maxPages = DEFAULT_MAX_EXPORT_PAGES;

    const params = new URLSearchParams();
    if (family !== "") params.append("family", family);
    if (species !== "") params.append("species", species);
    if (genus !== "") params.append("genus", genus);
    if (country !== "") params.append("country", country);
    if (dateFrom !== "") params.append("date_from", dateFrom);
    if (dateTo !== "") params.append("date_to", dateTo);
    if (resultLimit !== "") params.append("limit", resultLimit);
    if ((source === "inaturalist" || source === "both") && qualityGrade !== "") {
        params.append("quality_grade", qualityGrade);
    }

    return { source, family, species, genus, country, dateFrom, dateTo, qualityGrade, resultLimit, maxPages, params };
}

function triggerBlobDownload(blob, filename) {
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
}

function getPreviewRows(data, source) {
    const rows = Array.isArray(data) ? data : [];
    return rows.slice(0, 10);
}

function countCsvDataRows(text) {
    const value = String(text || "").replace(/^\uFEFF/, "");
    if (!value.trim()) return 0;

    let records = 0;
    let hasContent = false;
    let inQuotes = false;

    for (let index = 0; index < value.length; index += 1) {
        const char = value[index];
        const next = value[index + 1];

        if (char === '"') {
            if (inQuotes && next === '"') {
                index += 1;
            } else {
                inQuotes = !inQuotes;
            }
            hasContent = true;
        } else if ((char === "\n" || char === "\r") && !inQuotes) {
            if (hasContent) records += 1;
            hasContent = false;
            if (char === "\r" && next === "\n") index += 1;
        } else if (!/\s/.test(char)) {
            hasContent = true;
        }
    }

    if (hasContent) records += 1;
    return Math.max(0, records - 1);
}

async function countCsvBlobRows(blob) {
    try {
        return countCsvDataRows(await blob.text());
    } catch {
        return null;
    }
}

function formatCitationDate(date) {
    const safeDate = date instanceof Date && !Number.isNaN(date.getTime()) ? date : new Date();
    const pad = (value) => String(value).padStart(2, "0");
    const day = pad(safeDate.getDate());
    const month = pad(safeDate.getMonth() + 1);
    const year = safeDate.getFullYear();
    const hours = pad(safeDate.getHours());
    const minutes = pad(safeDate.getMinutes());
    return `${year}-${month}-${day} at ${hours}:${minutes}`;
}

function hasIucnEnrichment(data) {
    return (Array.isArray(data) ? data : []).some((row) => row && (
        Object.prototype.hasOwnProperty.call(row, "iucn_status")
        || Object.prototype.hasOwnProperty.call(row, "iucn_lookup_status")
        || Object.prototype.hasOwnProperty.call(row, "iucn_assessment_id")
        || Object.prototype.hasOwnProperty.call(row, "redListCategory")
        || Object.prototype.hasOwnProperty.call(row, "status")
    ));
}

function buildCitationSources(source, data) {
    const normalizedSource = normalizeSource(source);
    const sources = new Set();

    if (normalizedSource === "both") {
        Object.values(SOURCE_LABELS).forEach((label) => sources.add(label));
    } else {
        sources.add(SOURCE_LABELS[normalizedSource] || "GBIF");
    }

    (Array.isArray(data) ? data : []).forEach((row) => {
        const sourceName = row && row.source_bdd ? String(row.source_bdd).trim() : "";
        if (sourceName && sourceName !== "Not provided") sources.add(sourceName);
    });

    if (hasIucnEnrichment(data)) sources.add("IUCN");

    return Array.from(sources);
}

function hideCitationBox() {
    currentCitationText = "";
    if (citationBox) citationBox.hidden = true;
    if (citationFeedback) citationFeedback.textContent = "";
}

function showCitationBox(source, data, launchedAt) {
    if (!citationBox || !Array.isArray(data) || data.length === 0) {
        hideCitationBox();
        return;
    }

    const citationDate = formatCitationDate(launchedAt);
    const sources = buildCitationSources(source, data).join(", ");
    currentCitationText = [
        "Data obtained through BioData Explorer.",
        `Sources: ${sources}.`,
        `Search performed on ${citationDate}.`,
    ].join("\n");

    citationBox.hidden = false;
    if (citationFeedback) citationFeedback.textContent = "";
}

function renderResults(data, source, totalCount) {
    resultsBody.innerHTML = "";

    if (!Array.isArray(data) || data.length === 0) {
        hideCitationBox();
        countText.textContent = "0 result found.";
        resultsBody.innerHTML = `
            <tr>
                <td colspan="11" class="empty-state">
                    No results found.
                </td>
            </tr>
        `;
        return;
    }

    const firstTen = getPreviewRows(data, source);
    countText.textContent = "CSV row count will appear after download.";

    function getIucnValue(item) {
        return item.status || item.iucn_status || item.redListCategory || "Not provided";
    }

    firstTen.forEach(function (item) {
        const row = document.createElement("tr");
        const qualityGrade = item.quality_grade || (item.source_bdd === "iNaturalist" ? "Not provided" : "Not applicable");
        row.innerHTML = `
            <td>${item.source_bdd || "Not provided"}</td>
            <td>${item.country || "Not provided"}</td>
            <td>${item.coordinates || "Not provided"}</td>
            <td>${item.eventDate || "Not provided"}</td>
            <td>${item.basisOfRecord || "Not provided"}</td>
            <td>${item.datasetName || "Not provided"}</td>
            <td>${item.family || "Not provided"}</td>
            <td>${item.genus || "Not provided"}</td>
            <td>${item.species || "Not provided"}</td>
            <td><span class="quality-badge">${qualityGrade}</span></td>
            <td>${getIucnValue(item)}</td>
        `;
        resultsBody.appendChild(row);
    });
}

function renderSearchInProgress(source) {
    hideCitationBox();
    const labels = {
        gbif: "GBIF",
        silene_expert: "Silene Expert",
        inaturalist: "iNaturalist",
        steli: "STELI",
        both: "Combined",
    };
    countText.textContent = "Search in progress.";
    resultsBody.innerHTML = `
        <tr>
            <td colspan="11" class="empty-state">
                Searching ${labels[source] || "selected source"}...
            </td>
        </tr>
    `;
}

function saveLastSearch(payload) {
    try {
        const savedAt = payload.savedAt instanceof Date ? payload.savedAt.toISOString() : new Date().toISOString();
        const fullData = Array.isArray(payload.data) ? payload.data : [];
        const storedData = fullData.slice(0, STORED_RESULTS_LIMIT);
        const resultCount = Number.isFinite(Number(payload.resultCount)) ? Number(payload.resultCount) : fullData.length;
        const entry = {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            savedAt,
            params: payload.params,
            result_count: resultCount,
            data: storedData,
        };

        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(entry)
        );
        // Dedicated dashboard dataset: keep a recent sample to avoid localStorage quota failures.
        localStorage.setItem(LAST_RESULTS_KEY, JSON.stringify({ data: storedData, result_count: resultCount }));

        const rawHistory = localStorage.getItem(HISTORY_KEY);
        const history = rawHistory ? JSON.parse(rawHistory) : [];
        const nextHistory = [entry, ...(Array.isArray(history) ? history : [])].slice(0, 10);
        localStorage.setItem(HISTORY_KEY, JSON.stringify(nextHistory));
    } catch {
        // ignore quota / private mode issues
    }
}

function restoreLastSearch() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;

        const saved = JSON.parse(raw);
        if (!saved || !Array.isArray(saved.data)) return;

        if (saved.params) {
            activeSource = normalizeSource(saved.params.source || "gbif");
            if (sourceSelect) sourceSelect.value = activeSource;
            familyInput.value = saved.params.family || "";
            speciesInput.value = saved.params.species || "";
            genusInput.value = saved.params.genus || "";
            countryInput.value = saved.params.country || "";
            if (dateFromInput) dateFromInput.value = saved.params.dateFrom || "";
            if (dateToInput) dateToInput.value = saved.params.dateTo || "";
            if (qualityGradeInput) qualityGradeInput.value = saved.params.qualityGrade || "";
            syncSourceCards();
        }

        renderResults(saved.data, saved.params && saved.params.source, saved.result_count);
        showCitationBox(saved.params && saved.params.source, saved.data, saved.savedAt ? new Date(saved.savedAt) : new Date());
        setMessage("Results restored after reload.", "neutral");
    } catch {
        // ignore parse errors
    }
}

function setMessage(text, type) {
    message.textContent = text;
    message.className = "message-pill";
    if (type === "success") message.classList.add("success");
    if (type === "error") message.classList.add("error");
    if (type === "neutral") message.classList.add("neutral");
}

async function readErrorDetail(response, fallback) {
    let detail = "";
    try {
        const payload = await response.clone().json();
        detail = payload && payload.detail ? String(payload.detail) : "";
    } catch {
        try {
            detail = await response.clone().text();
        } catch {
            detail = "";
        }
    }
    return detail || `${fallback} (${response.status})`;
}

function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return "0 KB";
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatSeconds(seconds) {
    const value = Math.max(0, Math.round(Number(seconds || 0)));
    if (value < 60) return `${value} s`;
    const minutes = Math.floor(value / 60);
    const rest = value % 60;
    return `${minutes} min ${rest} s`;
}

function showDownloadProgress(text, value, percent, indeterminate) {
    if (!downloadProgress || !downloadProgressText || !downloadProgressValue || !downloadProgressBar) return;
    downloadProgress.hidden = false;
    downloadProgress.classList.toggle("indeterminate", Boolean(indeterminate));
    downloadProgressText.textContent = text;
    downloadProgressValue.textContent = indeterminate ? "In progress" : value;
    downloadProgressBar.style.width = indeterminate ? "40%" : `${Math.max(0, Math.min(100, Number(percent || 0)))}%`;
}

function hideDownloadProgress() {
    if (!downloadProgress) return;
    downloadProgress.hidden = true;
    downloadProgress.classList.remove("indeterminate");
    if (downloadProgressBar) downloadProgressBar.style.width = "0%";
}

async function downloadBlobWithProgress(url) {
    const startedAt = Date.now();
    let timer = window.setInterval(() => {
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        showDownloadProgress(`Preparing CSV... ${elapsed} s`, "In progress", 0, true);
    }, 1000);

    showDownloadProgress("Preparing CSV...", "In progress", 0, true);
    let response;
    try {
        response = await authFetch(url);
    } finally {
        if (timer) {
            window.clearInterval(timer);
            timer = null;
        }
    }

    if (!response.ok) {
        let detail = "";
        try {
            const payload = await response.clone().json();
            detail = payload && payload.detail ? String(payload.detail) : "";
        } catch {
            try {
                detail = await response.clone().text();
            } catch {
                detail = "";
            }
        }
        throw new Error(detail || `CSV error (${response.status})`);
    }

    const total = Number(response.headers.get("Content-Length") || 0);
    const contentType = response.headers.get("Content-Type") || "text/csv;charset=utf-8";

    if (!response.body) {
        showDownloadProgress("Downloading CSV...", "...", 0, true);
        const blob = await response.blob();
        showDownloadProgress("Download complete.", "100%", 100, false);
        return blob;
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

        const elapsedSeconds = Math.max(0.1, (Date.now() - downloadStartedAt) / 1000);
        if (total > 0) {
            const percent = Math.min(100, Math.round((received / total) * 100));
            const speed = received / elapsedSeconds;
            const remainingSeconds = speed > 0 ? (total - received) / speed : 0;
            showDownloadProgress(
                `CSV download: ${percent}% - ${formatBytes(received)} / ${formatBytes(total)} - ${formatSeconds(remainingSeconds)}`,
                `${percent}%`,
                percent,
                false
            );
        } else {
            showDownloadProgress(
                `CSV download in progress - ${formatBytes(received)} received`,
                "Calculating...",
                35,
                true
            );
        }
    }

    showDownloadProgress("Download complete.", "100%", 100, false);
    return new Blob(chunks, { type: contentType });
}

function syncSourceCards() {
    const currentSource = normalizeSource(activeSource || (sourceSelect && sourceSelect.value));
    activeSource = currentSource;
    if (sourceSelect) sourceSelect.value = currentSource;
    sourceCards.forEach((card) => {
        const isActive = normalizeSource(card.dataset.source) === currentSource;
        card.classList.toggle("active", isActive);
        card.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    if (qualityGradeInput) {
        qualityGradeInput.disabled = currentSource !== "inaturalist" && currentSource !== "both";
    }
    if (sourceHint) {
        const labels = {
            gbif: "GBIF occurrence search with standardized CSV export.",
            silene_expert: "Silene Expert search with automatic token refresh.",
            inaturalist: "iNaturalist observations with selectable quality grade.",
            steli: "STELI odonate monitoring via OpenObs/INPN when an endpoint is configured.",
            both: "Combined export runs GBIF, Silene Expert, iNaturalist and STELI in parallel.",
        };
        sourceHint.textContent = labels[currentSource] || labels.gbif;
    }
}

async function runSearch() {
    const { source, family, species, genus, country, dateFrom, dateTo, qualityGrade, resultLimit, maxPages, params } =
        getQueryParams();
    const launchedAt = new Date();
    const currentRunId = searchRunId + 1;
    searchRunId = currentRunId;

    if (searchAbortController) {
        searchAbortController.abort();
    }
    searchAbortController = new AbortController();
    let searchTimedOut = false;
    const searchTimeoutId = window.setTimeout(() => {
        searchTimedOut = true;
        if (searchAbortController) searchAbortController.abort();
    }, SEARCH_TIMEOUT_MS);
    params.set("_", String(Date.now()));

    if (dateFrom && dateTo && dateFrom > dateTo) {
        setMessage("Error: date_from must be before date_to.", "error");
        return;
    }

    try {
        setMessage("Search in progress...", "neutral");
        renderSearchInProgress(source);
        setLoading(true);

        let data = [];

        if (source === "gbif") {
            const url = `${API_URL}/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await authFetch(url, { cache: "no-store", signal: searchAbortController.signal });
            if (!response.ok) throw new Error(await readErrorDetail(response, "GBIF API error"));
            data = await response.json();
        } else if (source === "silene_expert") {
            // Mapping route applies family/genus/species/country filters server-side.
            const url = `${API_URL}/silene-expert/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await authFetch(url, { cache: "no-store", signal: searchAbortController.signal });
            if (!response.ok) throw new Error(await readErrorDetail(response, "Silene Expert API error"));
            data = await response.json();
        } else if (source === "inaturalist") {
            const url = `${API_URL}/inaturalist/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await authFetch(url, { cache: "no-store", signal: searchAbortController.signal });
            if (!response.ok) throw new Error(await readErrorDetail(response, "iNaturalist API error"));
            data = await response.json();
        } else if (source === "steli") {
            const url = `${API_URL}/steli/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await authFetch(url, { cache: "no-store", signal: searchAbortController.signal });
            if (!response.ok) throw new Error(await readErrorDetail(response, "STELI API error"));
            data = await response.json();
        } else if (source === "both") {
            // Combined endpoint: one call and one server-side CSV.
            const url = `${API_URL}/combined/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await authFetch(url, { cache: "no-store", signal: searchAbortController.signal });
            if (!response.ok) throw new Error(await readErrorDetail(response, "Combined API error"));
            data = await response.json();
        }

        if (currentRunId !== searchRunId) return;

        renderResults(data, source);
        showCitationBox(source, data, launchedAt);
        saveLastSearch({
            params: { source, family, species, genus, country, dateFrom, dateTo, qualityGrade, resultLimit, maxPages },
            data,
            resultCount: data.length,
            savedAt: launchedAt,
        });

        setMessage("Search completed.", "success");
    } catch (error) {
        if (error && error.name === "AbortError") {
            if (searchTimedOut && currentRunId === searchRunId) {
                setMessage("Error: search timed out. Try a smaller search or another source.", "error");
            }
            return;
        }
        console.error(error);
        if (currentRunId !== searchRunId) return;
        const detail = error && error.message ? ` ${error.message}` : "";
        setMessage(`Error: unable to retrieve data.${detail}`, "error");
    } finally {
        window.clearTimeout(searchTimeoutId);
        if (currentRunId === searchRunId) {
            setLoading(false);
            searchAbortController = null;
        }
    }
}

sourceCards.forEach((card) => {
    card.addEventListener("click", () => {
        handleSourceChange(card.dataset.source || "gbif");
    });
});

if (sourceSelect) {
    sourceSelect.addEventListener("change", () => handleSourceChange(sourceSelect.value));
}

searchBtn.addEventListener("click", runSearch);

[familyInput, speciesInput, genusInput, countryInput, dateFromInput, dateToInput, qualityGradeInput].filter(Boolean).forEach((input) => {
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            runSearch();
        }
    });
});

resetBtn.addEventListener("click", function () {
    setActiveSource("gbif");
    familyInput.value = "";
    speciesInput.value = "";
    genusInput.value = "";
    countryInput.value = "";
    if (dateFromInput) dateFromInput.value = "";
    if (dateToInput) dateToInput.value = "";
    if (qualityGradeInput) qualityGradeInput.value = "";

    setMessage("Ready to search.", "neutral");
    countText.textContent = "No search started.";
    hideCitationBox();

    try {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(LAST_RESULTS_KEY);
    } catch {}

    resultsBody.innerHTML = `
        <tr>
            <td colspan="11" class="empty-state">
                No results to display.
            </td>
        </tr>
    `;
});

if (copyCitationBtn) {
    copyCitationBtn.addEventListener("click", async () => {
        if (!currentCitationText) return;

        copyCitationBtn.disabled = true;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(currentCitationText);
            } else {
                const textarea = document.createElement("textarea");
                textarea.value = currentCitationText;
                textarea.setAttribute("readonly", "");
                textarea.style.position = "fixed";
                textarea.style.left = "-9999px";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                textarea.remove();
            }
            if (citationFeedback) citationFeedback.textContent = "Citation copied to the clipboard.";
        } catch (error) {
            console.error(error);
            if (citationFeedback) citationFeedback.textContent = "Unable to copy the citation.";
        } finally {
            copyCitationBtn.disabled = false;
        }
    });
}

exportBtn.addEventListener("click", function () {
    const { source, dateFrom, dateTo, maxPages, params } = getQueryParams();

    if (dateFrom && dateTo && dateFrom > dateTo) {
        setMessage("Error: date_from must be before date_to.", "error");
        return;
    }

    let url = "";
    let defaultFilename = "results.csv";
    params.set("limit", DEFAULT_EXPORT_PAGE_LIMIT);
    if (maxPages !== "") params.set("max_pages", maxPages);
    params.set("_", String(Date.now()));

    if (source === "gbif") {
        url = `${API_URL}/search/csv?${params.toString()}`;
        defaultFilename = "gbif_results.csv";
    } else if (source === "silene_expert") {
        url = `${API_URL}/silene-expert/search/csv?${params.toString()}`;
        defaultFilename = "silene_expert_results.csv";
    } else if (source === "inaturalist") {
        url = `${API_URL}/inaturalist/search/csv?${params.toString()}`;
        defaultFilename = "inaturalist_results.csv";
    } else if (source === "steli") {
        url = `${API_URL}/steli/search/csv?${params.toString()}`;
        defaultFilename = "steli_results.csv";
    } else {
        url = `${API_URL}/combined/search/csv?${params.toString()}`;
        defaultFilename = "gbif_silene_inaturalist_results.csv";
    }

    (async () => {
        try {
            setMessage("Preparing CSV...", "neutral");
            setLoading(true);

            const blob = await downloadBlobWithProgress(url);
            triggerBlobDownload(blob, defaultFilename);

            const csvRows = await countCsvBlobRows(blob);
            if (Number.isFinite(csvRows)) {
                countText.textContent = `${formatNumber(csvRows)} row(s) in the downloaded CSV. Preview still shows the first 10 most recent.`;
                setMessage(`CSV downloaded: ${formatNumber(csvRows)} row(s).`, "success");
            } else {
                setMessage("CSV downloaded.", "success");
            }
            window.setTimeout(hideDownloadProgress, 1200);
        } catch (error) {
            console.error(error);
            const detail = error && error.message ? ` ${error.message}` : "";
            setMessage(`Error: unable to download CSV.${detail}`, "error");
            showDownloadProgress("Download error.", "Error", 100, false);
        } finally {
            setLoading(false);
        }
    })();
});

syncSourceCards();
renderAuthBadge();
removeLegacySearchWidget();
restoreLastSearch();
