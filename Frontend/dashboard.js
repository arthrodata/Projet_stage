const STORAGE_KEY = getAuthStorageKey("biodiversity:last_search_v1");
const LAST_RESULTS_KEY = getAuthStorageKey("biodiversity_last_results");
const API_URL = window.API_URL;
const CONNECTED_SOURCES = ["GBIF", "Silene Expert", "iNaturalist", "STELI"];
const CSV_EXPORTS = ["GBIF", "Silene Expert", "iNaturalist", "STELI", "Combined"];
const IGNORED_SPECIES = new Set(["unknown", "non renseign\u00e9", "non renseigne", "not provided"]);
const SPECIES_COLORS = ["#2563eb", "#059669", "#7c3aed", "#f97316", "#dc2626"];
const GEO_COUNTRY_COLORS = ["#2563eb", "#059669", "#7c3aed", "#f97316", "#dc2626"];
const COUNTRY_ALIASES = {
    america: "United States",
    "etats unis": "United States",
    "etats-unis": "United States",
    "u s a": "United States",
    "united states of america": "United States",
    california: "United States",
    texas: "United States",
    florida: "United States",
    "new york": "United States",
    "south carolina": "United States",
    us: "United States",
    usa: "United States",
    uk: "United Kingdom",
    gb: "United Kingdom",
    gbr: "United Kingdom",
    "great britain": "United Kingdom",
    "royaume uni": "United Kingdom",
    "royaume-uni": "United Kingdom",
    "united kingdom of great britain and northern ireland": "United Kingdom",
    england: "United Kingdom",
    scotland: "United Kingdom",
    wales: "United Kingdom",
    "northern ireland": "United Kingdom",
    fr: "France",
    fra: "France",
    "france metropolitan": "France",
    "france metropolitaine": "France",
    de: "Germany",
    deu: "Germany",
    deutschland: "Germany",
    es: "Spain",
    esp: "Spain",
    espana: "Spain",
    it: "Italy",
    ita: "Italy",
    italia: "Italy",
    italie: "Italy",
    italien: "Italy",
    be: "Belgium",
    bel: "Belgium",
    ch: "Switzerland",
    che: "Switzerland",
    suisse: "Switzerland",
    nl: "Netherlands",
    nld: "Netherlands",
    "the netherlands": "Netherlands",
    holland: "Netherlands",
    at: "Austria",
    aut: "Austria",
    osterreich: "Austria",
    pt: "Portugal",
    prt: "Portugal",
    au: "Australia",
    aus: "Australia",
    nz: "New Zealand",
    nzl: "New Zealand",
    br: "Brazil",
    bra: "Brazil",
    brasil: "Brazil",
    brazilie: "Brazil",
    za: "South Africa",
    zaf: "South Africa",
    cn: "China",
    chn: "China",
    china: "China",
    jp: "Japan",
    jpn: "Japan",
    japan: "Japan",
    kr: "South Korea",
    kor: "South Korea",
    "south korea": "South Korea",
    "republic of korea": "South Korea",
    ca: "Canada",
    can: "Canada",
    canada: "Canada",
    cr: "Costa Rica",
    cri: "Costa Rica",
    "costa rica": "Costa Rica",
    mx: "Mexico",
    mex: "Mexico",
    mexico: "Mexico",
    pl: "Poland",
    pol: "Poland",
    polska: "Poland",
    ru: "Russia",
    rus: "Russia",
    russia: "Russia",
    tr: "Turkey",
    tur: "Turkey",
    turkiye: "Turkey",
    turkey: "Turkey",
    tw: "Taiwan",
    twn: "Taiwan",
    taiwan: "Taiwan",
    "chinese taipei": "Taiwan",
    my: "Malaysia",
    mys: "Malaysia",
    malaysia: "Malaysia",
    "frasers hill": "Malaysia",
    "fraser s hill": "Malaysia",
    th: "Thailand",
    tha: "Thailand",
    thailand: "Thailand",
    in: "India",
    ind: "India",
    india: "India",
    id: "Indonesia",
    idn: "Indonesia",
    indonesia: "Indonesia",
    no: "Norway",
    nor: "Norway",
    norway: "Norway",
    se: "Sweden",
    swe: "Sweden",
    sweden: "Sweden",
    hu: "Hungary",
    hun: "Hungary",
    hungary: "Hungary",
    ec: "Ecuador",
    ecu: "Ecuador",
    ecuador: "Ecuador",
    co: "Colombia",
    col: "Colombia",
    colombia: "Colombia",
    cl: "Chile",
    chl: "Chile",
    chile: "Chile",
    pe: "Peru",
    per: "Peru",
    peru: "Peru",
    gambia: "Gambia",
    gm: "Gambia",
    gmb: "Gambia",
    nsw: "Australia",
    "new south wales": "Australia",
    victoria: "Australia",
    queensland: "Australia",
    "french guiana": "French Guiana",
    "guyane francaise": "French Guiana",
    "franzosisch guyana": "French Guiana",
    czesko: "Czechia",
    cesko: "Czechia",
    czechia: "Czechia",
    armenie: "Armenia",
    armenia: "Armenia",
    kroatie: "Croatia",
    croatia: "Croatia",
    "cote d ivoire": "Cote d'Ivoire",
    "cote divoire": "Cote d'Ivoire",
    "ivory coast": "Cote d'Ivoire",
    georgia: "Georgia",
    romania: "Romania",
    rumanien: "Romania",
    slovenie: "Slovenia",
    slovenia: "Slovenia",
    "coree du sud": "South Korea",
    panama: "Panama",
    danemark: "Denmark",
    denmark: "Denmark",
    belgie: "Belgium",
    greece: "Greece",
    bresil: "Brazil",
    madagascar: "Madagascar",
    "hong kong": "Hong Kong",
    macau: "Macau",
    "united arab emirates": "United Arab Emirates",
    uae: "United Arab Emirates",
    magyarorszag: "Hungary",
    "moth light 102 queen anne bridge road": "United States",
    "suffolk imprecise location to obscure my garden": "United Kingdom",
    "markische schweiz": "Germany",
    "roberts bird sanctuary": "United States",
    "pedregal abajo reserva comunal el siea": "Panama",
    "kemensah hiking trail part 1 kebun pacik sadik": "Malaysia",
    marica: "Brazil",
    "sitio cumati": "Brazil",
    "rio guapore sao francisco do guapore ro": "Brazil",
    "estacion biologica monte verde": "Costa Rica",
    mosfellsbr: "Iceland",
    mosfellsbaer: "Iceland",
};
const COUNTRY_TEXT_MARKERS = [
    ["日本", "Japan"],
    ["中国", "China"],
    ["中华人民共和国", "China"],
    ["山东", "China"],
    ["北京", "China"],
    ["上海", "China"],
    ["广东", "China"],
    ["浙江", "China"],
    ["连珠山头", "China"],
    ["杭州", "China"],
    ["南京", "China"],
    ["安徽", "China"],
    ["海南", "China"],
    ["宝华山", "China"],
    ["台州", "China"],
    ["대한민국", "South Korea"],
    ["한국", "South Korea"],
    ["갈재", "South Korea"],
    ["흑성산", "South Korea"],
    ["태조산", "South Korea"],
    ["Россия", "Russia"],
    ["Казахстан", "Kazakhstan"],
    ["ישראל", "Israel"],
    ["צפון הכנרת", "Israel"],
    ["גבעת זאב", "Israel"],
    ["Кыргызстан", "Kyrgyzstan"],
    ["Україна", "Ukraine"],
    ["Грузия", "Georgia"],
    ["Беларусь", "Belarus"],
    ["Южная Африка", "South Africa"],
    ["Япония", "Japan"],
    ["España", "Spain"],
    ["México", "Mexico"],
    ["Österreich", "Austria"],
    ["Rakúsko", "Austria"],
    ["Türkiye", "Turkey"],
    ["Türkei", "Turkey"],
    ["ประเทศไทย", "Thailand"],
    ["Guyane française", "French Guiana"],
    ["台灣", "Taiwan"],
    ["臺灣", "Taiwan"],
    ["台湾", "Taiwan"],
    ["臺中", "Taiwan"],
    ["新莊", "Taiwan"],
    ["大山北月", "Taiwan"],
    ["香港", "Hong Kong"],
    ["澳門", "Macau"],
    ["马来西亚", "Malaysia"],
    ["馬來西亞", "Malaysia"],
    ["秘鲁", "Peru"],
    ["秘魯", "Peru"],
    ["馬達加斯加", "Madagascar"],
    ["마다가스카르", "Madagascar"],
    ["Ελλάδα", "Greece"],
    ["Sharjah", "United Arab Emirates"],
    ["Chocó", "Colombia"],
];
let geoLeafletMap = null;

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
    for (const value of values || []) {
        const text = String(value || "").trim();
        const lower = text.toLowerCase();
        if (text !== "" && !IGNORED_SPECIES.has(lower)) {
            out.add(text);
        }
    }
    return out;
}

function readLastSearch() {
    const rawLegacy = localStorage.getItem(STORAGE_KEY);
    const savedLegacy = rawLegacy ? safeParseJson(rawLegacy) : null;

    const rawResults = localStorage.getItem(LAST_RESULTS_KEY);
    const savedResults = rawResults ? safeParseJson(rawResults) : null;
    const resultsData = Array.isArray(savedResults)
        ? savedResults
        : savedResults && Array.isArray(savedResults.data)
          ? savedResults.data
          : null;
    const resultCount = savedResults && Number.isFinite(Number(savedResults.result_count))
        ? Number(savedResults.result_count)
        : null;

    if (savedLegacy && Array.isArray(savedLegacy.data)) {
        return resultsData ? { ...savedLegacy, data: resultsData, result_count: resultCount || savedLegacy.result_count } : savedLegacy;
    }
    if (resultsData) return { data: resultsData, result_count: resultCount, savedAt: "" };
    return null;
}

function normalizeSpecies(value) {
    const text = String(value || "").trim();
    if (text === "" || IGNORED_SPECIES.has(text.toLowerCase())) return "";
    return text;
}

function normalizeCountry(value) {
    const text = String(value || "").trim();
    if (text === "" || IGNORED_SPECIES.has(text.toLowerCase())) return "";
    if (/^\d+$/.test(text)) return "";
    const key = text
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replaceAll("&", " and ")
        .replaceAll(".", "")
        .replaceAll(",", " ")
        .replaceAll("(", " ")
        .replaceAll(")", " ")
        .replaceAll("'", " ")
        .replaceAll("\u2019", " ")
        .replaceAll("-", " ")
        .trim()
        .replace(/\s+/g, " ");
    if (COUNTRY_ALIASES[key]) return COUNTRY_ALIASES[key];
    for (const [marker, country] of COUNTRY_TEXT_MARKERS) {
        if (text.includes(marker)) return country;
    }
    const searchable = ` ${key} `;
    const aliases = Object.keys(COUNTRY_ALIASES).sort((a, b) => b.length - a.length);
    for (const alias of aliases) {
        if (alias.length >= 5 && searchable.includes(` ${alias} `)) return COUNTRY_ALIASES[alias];
    }
    return text;
}

function parseCoordinates(value) {
    const text = String(value || "").trim();
    if (text === "" || IGNORED_SPECIES.has(text.toLowerCase())) return null;

    const parts = text.split(",").map((part) => Number(String(part).trim()));
    if (parts.length < 2 || !Number.isFinite(parts[0]) || !Number.isFinite(parts[1])) return null;

    const lat = parts[0];
    const lon = parts[1];
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;

    return { lat, lon };
}

function calculateSpeciesDistribution(rows) {
    const counts = new Map();

    // Count each valid species from the last saved search.
    for (const item of rows || []) {
        const species = normalizeSpecies(item && item.species);
        if (!species) continue;
        counts.set(species, (counts.get(species) || 0) + 1);
    }

    return Array.from(counts, ([species, count]) => ({ species, count }))
        .sort((a, b) => b.count - a.count || a.species.localeCompare(b.species, "en"))
        .slice(0, 5);
}

function renderSpeciesDistribution(distribution) {
    const chart = document.getElementById("speciesChart");
    const legend = document.getElementById("speciesLegend");
    if (!chart || !legend) return;

    chart.innerHTML = "";
    legend.innerHTML = "";

    if (!Array.isArray(distribution) || distribution.length === 0) {
        const empty = document.createElement("p");
        empty.className = "species-empty-state";
        empty.textContent = "No data available to generate the chart.";
        chart.appendChild(empty);
        return;
    }

    const maxCount = Math.max(...distribution.map((item) => item.count));

    // Build native horizontal bars without introducing a charting dependency.
    distribution.forEach((item, index) => {
        const color = SPECIES_COLORS[index % SPECIES_COLORS.length];
        const percent = maxCount > 0 ? Math.max(8, Math.round((item.count / maxCount) * 100)) : 0;

        const row = document.createElement("div");
        row.className = "species-chart-row";

        const label = document.createElement("div");
        label.className = "species-chart-label";
        label.textContent = item.species;

        const track = document.createElement("div");
        track.className = "species-chart-track";

        const bar = document.createElement("div");
        bar.className = "species-chart-bar";
        bar.style.width = `${percent}%`;
        bar.style.background = color;
        bar.textContent = formatNumber(item.count);
        bar.setAttribute("aria-label", `${item.species}: ${formatNumber(item.count)} occurrence(s)`);

        track.appendChild(bar);
        row.appendChild(label);
        row.appendChild(track);
        chart.appendChild(row);

        const legendItem = document.createElement("div");
        legendItem.className = "species-legend-item";

        const swatch = document.createElement("span");
        swatch.className = "species-legend-swatch";
        swatch.style.background = color;

        const text = document.createElement("span");
        text.textContent = item.species;

        legendItem.appendChild(swatch);
        legendItem.appendChild(text);
        legend.appendChild(legendItem);
    });
}

function buildCountryDistribution(results) {
    const grouped = new Map();

    // Group by country and keep every coordinate point from the last saved search.
    for (const item of results || []) {
        const coords = parseCoordinates(item && item.coordinates);
        const country = normalizeCountry(item && item.country) || (coords ? "Country not provided" : "");
        if (!country) continue;

        if (!grouped.has(country)) {
            grouped.set(country, { country, count: 0, points: [] });
        }

        const entry = grouped.get(country);
        entry.count += 1;

        if (coords) {
            entry.points.push({
                ...coords,
                species: normalizeSpecies(item && item.species),
            });
        }
    }

    return Array.from(grouped.values())
        .sort((a, b) => b.count - a.count || a.country.localeCompare(b.country, "en"));
}

function appendGeoRoute(map) {
    const route = document.createElement("div");
    route.className = "geo-route";
    route.setAttribute("aria-hidden", "true");
    map.appendChild(route);
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function renderGeoEmptyState(map, text) {
    const empty = document.createElement("p");
    empty.className = "geo-empty-state";
    empty.textContent = text;
    map.appendChild(empty);
}

function resetGeoMap() {
    if (geoLeafletMap) {
        geoLeafletMap.remove();
        geoLeafletMap = null;
    }
}

function renderGeoDistributionChart(data) {
    const map = document.getElementById("geoMap");
    if (!map) return;

    resetGeoMap();
    map.innerHTML = "";

    if (!Array.isArray(data) || data.length === 0) {
        appendGeoRoute(map);
        renderGeoEmptyState(map, "No data available to generate the geographic distribution.");
        return;
    }

    const countriesWithPoints = data.filter((item) => Array.isArray(item.points) && item.points.length > 0);
    if (countriesWithPoints.length === 0) {
        appendGeoRoute(map);
        renderGeoEmptyState(map, "No coordinates available to display points on the map.");
        return;
    }

    if (typeof L === "undefined") {
        appendGeoRoute(map);
        renderGeoEmptyState(map, "The interactive map could not be loaded.");
        return;
    }

    const leafletContainer = document.createElement("div");
    leafletContainer.className = "geo-leaflet-map";
    map.appendChild(leafletContainer);

    geoLeafletMap = L.map(leafletContainer, {
        scrollWheelZoom: true,
        worldCopyJump: true,
    }).setView([20, 0], 2);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(geoLeafletMap);

    const bounds = [];

    countriesWithPoints.forEach((item, index) => {
        const color = GEO_COUNTRY_COLORS[index % GEO_COUNTRY_COLORS.length];
        const latLngs = item.points.map((point) => [point.lat, point.lon]);
        const averageLat = latLngs.reduce((sum, point) => sum + point[0], 0) / latLngs.length;
        const averageLon = latLngs.reduce((sum, point) => sum + point[1], 0) / latLngs.length;

        item.points.forEach((point, pointIndex) => {
            bounds.push([point.lat, point.lon]);

            L.circleMarker([point.lat, point.lon], {
                radius: 7,
                color: "#ffffff",
                weight: 2,
                fillColor: color,
                fillOpacity: 0.88,
            })
                .bindPopup(`
                    <strong>${escapeHtml(item.country)}</strong><br>
                    ${escapeHtml(point.species || "Occurrence")}<br>
                    ${formatNumber(item.count)} occurrence(s) in this country<br>
                    Point ${pointIndex + 1} / ${item.points.length}<br>
                    ${point.lat}, ${point.lon}
                `)
                .addTo(geoLeafletMap);
        });

        L.marker([averageLat, averageLon], {
            icon: L.divIcon({
                className: "geo-country-marker",
                html: `
                    <div class="geo-country-marker-inner" style="--marker-color: ${color}">
                        <strong>${escapeHtml(item.country)}</strong>
                        <span>${formatNumber(item.count)} occurrence(s)</span>
                    </div>
                `,
                iconSize: [138, 48],
                iconAnchor: [69, 24],
            }),
            interactive: false,
        }).addTo(geoLeafletMap);
    });

    if (bounds.length === 1) {
        geoLeafletMap.setView(bounds[0], 8);
    } else {
        geoLeafletMap.fitBounds(bounds, { padding: [34, 34], maxZoom: 7 });
    }

    window.setTimeout(() => geoLeafletMap && geoLeafletMap.invalidateSize(), 0);
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
        td.textContent = "No saved search.";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    rows.forEach((item) => {
        const tr = document.createElement("tr");
        appendCell(tr, pick(item, ["source_bdd"]) || "Not provided");
        appendCell(tr, pick(item, ["country"]) || "Not provided");
        appendCell(tr, pick(item, ["species"]) || "Not provided");
        appendCell(tr, pick(item, ["eventDate"]) || "Not provided");
        tbody.appendChild(tr);
    });
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

async function readServerLastSearch() {
    const response = await authFetch(`${API_URL}/history?limit=1`);
    if (!response.ok) throw new Error("History API error");
    const history = await response.json();
    return Array.isArray(history) && history.length > 0 ? history[0] : null;
}

function searchTimestamp(entry) {
    const raw = entry && (entry.savedAt || entry.created_at || entry.createdAt || entry.timestamp);
    const timestamp = raw ? Date.parse(raw) : 0;
    return Number.isFinite(timestamp) ? timestamp : 0;
}

async function readLatestSearch() {
    const localSearch = readLastSearch();
    let serverSearch = null;
    try {
        serverSearch = await readServerLastSearch();
    } catch (error) {
        console.error(error);
    }

    if (!serverSearch) return localSearch;
    if (!localSearch) return serverSearch;
    return searchTimestamp(localSearch) > searchTimestamp(serverSearch) ? localSearch : serverSearch;
}

let refreshTimer = null;

function scheduleDashboardRefresh() {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(initDashboard, 100);
}

async function initDashboard() {
    const msg = document.getElementById("dashMessage");

    try {
        if (window.location && window.location.protocol === "file:") {
            if (msg) msg.textContent = "Open the page via http://127.0.0.1:8081 to read the latest search.";
        } else if (msg) {
            msg.textContent = "Loading...";
        }

        const saved = await readLatestSearch();
        const data = saved && Array.isArray(saved.data) ? saved.data : [];

        const connectedSources = CONNECTED_SOURCES.length;
        const csvExports = CSV_EXPORTS.length;

        const occurrences = Number.isFinite(Number(saved && saved.result_count)) ? Number(saved.result_count) : data.length;
        const uniqueSpecies = uniqNonEmpty(data.map((item) => item && item.species)).size;
        const detectedSources = uniqNonEmpty(data.map((item) => item && item.source_bdd)).size;

        setText("statSources", String(connectedSources));
        setText("statExports", String(csvExports));
        setText("statOccurrences", formatNumber(occurrences));
        setText("statSpecies", formatNumber(uniqueSpecies));
        setText(
            "statSourcesMeta",
            occurrences > 0 ? `${formatNumber(detectedSources)} source(s) detected` : `${connectedSources} configured`
        );
        setText("statExportsMeta", CSV_EXPORTS.join(" / "));
        renderSpeciesDistribution(calculateSpeciesDistribution(data));
        renderGeoDistributionChart(buildCountryDistribution(data));

        if (!saved || !Array.isArray(saved.data)) {
            if (msg && !(window.location && window.location.protocol === "file:")) {
                msg.textContent = "No saved search.";
            }
            renderLastRows([]);
            return;
        }

        if (msg) msg.textContent = "Latest search loaded";

        renderLastRows(data.slice(0, 5));
    } catch (error) {
        console.error(error);
        if (msg) msg.textContent = "Dashboard error.";
        renderLastRows([]);
        renderSpeciesDistribution([]);
        renderGeoDistributionChart([]);
    }
}

requireAuth();
renderAuthBadge();
initDashboard();

window.addEventListener("storage", (event) => {
    if (event.key === LAST_RESULTS_KEY || event.key === STORAGE_KEY) {
        scheduleDashboardRefresh();
    }
});

window.addEventListener("focus", scheduleDashboardRefresh);

document.addEventListener("visibilitychange", () => {
    if (!document.hidden) scheduleDashboardRefresh();
});
