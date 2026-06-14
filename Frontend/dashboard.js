const STORAGE_KEY = "biodiversity:last_search_v1";
const LAST_RESULTS_KEY = "biodiversity_last_results";
const IGNORED_SPECIES = new Set(["unknown", "non renseign\u00e9", "non renseigne", "not provided"]);
const SPECIES_COLORS = ["#2563eb", "#059669", "#7c3aed", "#f97316", "#dc2626"];
const GEO_COUNTRY_COLORS = ["#2563eb", "#059669", "#7c3aed", "#f97316", "#dc2626"];
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
        if (text !== "" && !IGNORED_SPECIES.has(lower)) {
            out.add(text);
        }
    }
    return out;
}

function readLastSearch() {
    const rawResults = localStorage.getItem(LAST_RESULTS_KEY);
    const savedResults = rawResults ? safeParseJson(rawResults) : null;
    if (Array.isArray(savedResults)) return { data: savedResults };
    if (savedResults && Array.isArray(savedResults.data)) return savedResults;

    const rawLegacy = localStorage.getItem(STORAGE_KEY);
    const savedLegacy = rawLegacy ? safeParseJson(rawLegacy) : null;
    return savedLegacy && Array.isArray(savedLegacy.data) ? savedLegacy : null;
}

function normalizeSpecies(value) {
    const text = String(value || "").trim();
    if (text === "" || IGNORED_SPECIES.has(text.toLowerCase())) return "";
    return text;
}

function normalizeCountry(value) {
    const text = String(value || "").trim();
    if (text === "" || IGNORED_SPECIES.has(text.toLowerCase())) return "";
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
        .sort((a, b) => b.count - a.count || a.species.localeCompare(b.species, "fr"))
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
        empty.textContent = "Aucune donn\u00e9e disponible pour g\u00e9n\u00e9rer le graphique.";
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

    // Group by country and keep the first 10 coordinate points for each country.
    for (const item of results || []) {
        const country = normalizeCountry(item && item.country);
        if (!country) continue;

        if (!grouped.has(country)) {
            grouped.set(country, { country, count: 0, points: [] });
        }

        const entry = grouped.get(country);
        entry.count += 1;

        const coords = parseCoordinates(item && item.coordinates);
        if (coords && entry.points.length < 10) {
            entry.points.push({
                ...coords,
                species: normalizeSpecies(item && item.species),
            });
        }
    }

    return Array.from(grouped.values())
        .sort((a, b) => b.count - a.count || a.country.localeCompare(b.country, "fr"))
        .slice(0, 5);
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
        renderGeoEmptyState(map, "Aucune donn\u00e9e disponible pour g\u00e9n\u00e9rer la r\u00e9partition g\u00e9ographique.");
        return;
    }

    const countriesWithPoints = data.filter((item) => Array.isArray(item.points) && item.points.length > 0);
    if (countriesWithPoints.length === 0) {
        appendGeoRoute(map);
        renderGeoEmptyState(map, "Aucune coordonn\u00e9e disponible pour afficher les points sur la carte.");
        return;
    }

    if (typeof L === "undefined") {
        appendGeoRoute(map);
        renderGeoEmptyState(map, "La carte interactive n'a pas pu \u00eatre charg\u00e9e.");
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
                    ${formatNumber(item.count)} occ. dans le pays<br>
                    Point ${pointIndex + 1} / ${Math.min(10, item.points.length)}<br>
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
                        <span>${formatNumber(item.count)} occ.</span>
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

        const saved = readLastSearch();
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
        renderSpeciesDistribution(calculateSpeciesDistribution(data));
        renderGeoDistributionChart(buildCountryDistribution(data));

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
        renderSpeciesDistribution([]);
        renderGeoDistributionChart([]);
    }
}

initDashboard();

window.addEventListener("storage", (event) => {
    if (event.key === LAST_RESULTS_KEY || event.key === STORAGE_KEY) {
        initDashboard();
    }
});
