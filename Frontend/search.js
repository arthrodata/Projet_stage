console.log("search.js loaded");

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "biodiversity:last_search_v1";
const HISTORY_KEY = "biodiversity:search_history_v1";
const DEFAULT_RESULT_LIMIT = "100";
const DEFAULT_MAX_EXPORT_PAGES = "50";

const searchBtn = document.getElementById("searchBtn");
const resetBtn = document.getElementById("resetBtn");
const exportBtn = document.getElementById("exportBtn");

const resultsBody = document.getElementById("resultsBody");
const countText = document.getElementById("countText");
const message = document.getElementById("message");

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
    const source = ((sourceSelect && sourceSelect.value) || "gbif").trim();
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

function renderResults(data) {
    resultsBody.innerHTML = "";

    if (!Array.isArray(data) || data.length === 0) {
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

    const firstTen = data.slice(0, 10);
    countText.textContent = `${data.length} result(s) retrieved. Showing the first 10.`;

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

function applyFamilyFilterClientSide(data, family) {
    const fam = (family || "").trim().toLowerCase();
    if (!fam) return data;
    if (!Array.isArray(data)) return [];
    return data.filter((item) => ((item.family || "").toString().toLowerCase().includes(fam)));
}

function saveLastSearch(payload) {
    try {
        const entry = {
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            savedAt: new Date().toISOString(),
            params: payload.params,
            data: payload.data,
        };

        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(entry)
        );

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
            if (sourceSelect) sourceSelect.value = saved.params.source || "gbif";
            familyInput.value = saved.params.family || "";
            speciesInput.value = saved.params.species || "";
            genusInput.value = saved.params.genus || "";
            countryInput.value = saved.params.country || "";
            if (dateFromInput) dateFromInput.value = saved.params.dateFrom || "";
            if (dateToInput) dateToInput.value = saved.params.dateTo || "";
            if (qualityGradeInput) qualityGradeInput.value = saved.params.qualityGrade || "";
            syncSourceCards();
        }

        renderResults(saved.data);
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

function syncSourceCards() {
    const activeSource = ((sourceSelect && sourceSelect.value) || "gbif").trim();
    sourceCards.forEach((card) => {
        card.classList.toggle("active", card.dataset.source === activeSource);
    });
    if (qualityGradeInput) {
        qualityGradeInput.disabled = activeSource !== "inaturalist" && activeSource !== "both";
    }
    if (sourceHint) {
        const labels = {
            gbif: "GBIF occurrence search with standardized CSV export.",
            silene_expert: "Silene Expert search with automatic token refresh.",
            inaturalist: "iNaturalist observations with selectable quality grade.",
            both: "Combined export runs GBIF, Silene Expert and iNaturalist in parallel.",
        };
        sourceHint.textContent = labels[activeSource] || labels.gbif;
    }
}

async function runSearch() {
    const { source, family, species, genus, country, dateFrom, dateTo, qualityGrade, params } = getQueryParams();

    if (dateFrom && dateTo && dateFrom > dateTo) {
        setMessage("Error: date_from must be before date_to.", "error");
        return;
    }

    try {
        setMessage("Search in progress...", "neutral");
        setLoading(true);

        let data = [];

        if (source === "gbif") {
            const url = `${API_URL}/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("GBIF API error");
            data = await response.json();
        } else if (source === "silene_expert") {
            // Mapping route applies family/genus/species/country filters server-side.
            const url = `${API_URL}/silene-expert/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("Silene Expert API error");
            data = await response.json();
        } else if (source === "inaturalist") {
            const url = `${API_URL}/inaturalist/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("iNaturalist API error");
            data = await response.json();
        } else if (source === "both") {
            // Combined endpoint: one call and one server-side CSV.
            const url = `${API_URL}/combined/search?${params.toString()}`;
            console.log("Called URL:", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("Combined API error");
            data = await response.json();
        }

        // Safety filter: some sources can return empty or non-normalized families.
        data = applyFamilyFilterClientSide(data, family);

        renderResults(data);
        saveLastSearch({ params: { source, family, species, genus, country, dateFrom, dateTo, qualityGrade }, data });

        setMessage("Search completed.", "success");
    } catch (error) {
        console.error(error);
        setMessage("Error: unable to retrieve data.", "error");
    } finally {
        setLoading(false);
    }
}

sourceCards.forEach((card) => {
    card.addEventListener("click", () => {
        if (!sourceSelect) return;
        sourceSelect.value = card.dataset.source || "gbif";
        syncSourceCards();
    });
});

if (sourceSelect) {
    sourceSelect.addEventListener("change", syncSourceCards);
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
    if (sourceSelect) sourceSelect.value = "gbif";
    familyInput.value = "";
    speciesInput.value = "";
    genusInput.value = "";
    countryInput.value = "";
    if (dateFromInput) dateFromInput.value = "";
    if (dateToInput) dateToInput.value = "";
    if (qualityGradeInput) qualityGradeInput.value = "";

    setMessage("Ready to search.", "neutral");
    countText.textContent = "No search started.";

    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch {}

    resultsBody.innerHTML = `
        <tr>
            <td colspan="11" class="empty-state">
                No results to display.
            </td>
        </tr>
    `;
});

exportBtn.addEventListener("click", function () {
    const { source, dateFrom, dateTo, maxPages, params } = getQueryParams();

    if (dateFrom && dateTo && dateFrom > dateTo) {
        setMessage("Error: date_from must be before date_to.", "error");
        return;
    }

    let url = "";
    let defaultFilename = "resultats.csv";
    if (maxPages !== "") params.set("max_pages", maxPages);

    if (source === "gbif") {
        url = `${API_URL}/search/csv?${params.toString()}`;
        defaultFilename = "gbif_results.csv";
    } else if (source === "silene_expert") {
        url = `${API_URL}/silene-expert/search/csv?${params.toString()}`;
        defaultFilename = "silene_expert_results.csv";
    } else if (source === "inaturalist") {
        url = `${API_URL}/inaturalist/search/csv?${params.toString()}`;
        defaultFilename = "inaturalist_results.csv";
    } else {
        url = `${API_URL}/combined/search/csv?${params.toString()}`;
        defaultFilename = "gbif_silene_inaturalist_results.csv";
    }

    (async () => {
        try {
            setMessage("Generating CSV...", "neutral");
            setLoading(true);

            const response = await fetch(url);
            if (!response.ok) throw new Error("CSV error");

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);

            const a = document.createElement("a");
            a.href = objectUrl;
            a.download = defaultFilename;
            document.body.appendChild(a);
            a.click();
            a.remove();

            URL.revokeObjectURL(objectUrl);

            setMessage("CSV downloaded.", "success");
        } catch (error) {
            console.error(error);
            setMessage("Error: unable to download CSV.", "error");
        } finally {
            setLoading(false);
        }
    })();
});

syncSourceCards();
removeLegacySearchWidget();
restoreLastSearch();
