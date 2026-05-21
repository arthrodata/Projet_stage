console.log("search.js charge");

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "biodiversity:last_search_v1";

const searchBtn = document.getElementById("searchBtn");
const resetBtn = document.getElementById("resetBtn");
const exportBtn = document.getElementById("exportBtn");

const resultsBody = document.getElementById("resultsBody");
const countText = document.getElementById("countText");
const message = document.getElementById("message");

const familyInput = document.getElementById("family");
const speciesInput = document.getElementById("species");
const genusInput = document.getElementById("genus");
const countryInput = document.getElementById("country");

function setLoading(isLoading) {
    searchBtn.disabled = isLoading;
    resetBtn.disabled = isLoading;
    exportBtn.disabled = isLoading;
}

function getQueryParams() {
    const family = familyInput.value.trim();
    const species = speciesInput.value.trim();
    const genus = genusInput.value.trim();
    const country = countryInput.value.trim();

    const params = new URLSearchParams();
    if (family !== "") params.append("family", family);
    if (species !== "") params.append("species", species);
    if (genus !== "") params.append("genus", genus);
    if (country !== "") params.append("country", country);

    return { family, species, genus, country, params };
}

function afficherResultats(data) {
    resultsBody.innerHTML = "";

    if (!Array.isArray(data) || data.length === 0) {
        countText.textContent = "0 resultat trouve.";
        resultsBody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center text-muted">
                    Aucun resultat trouve.
                </td>
            </tr>
        `;
        return;
    }

    const firstTen = data.slice(0, 10);
    countText.textContent = `${data.length} resultat(s) recupere(s). Affichage des 10 premiers.`;

    firstTen.forEach(function (item) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${item.country || "Non renseigne"}</td>
            <td>${item.coordinates || "Non renseigne"}</td>
            <td>${item.eventDate || "Non renseigne"}</td>
            <td>${item.basisOfRecord || "Non renseigne"}</td>
            <td>${item.datasetName || "Non renseigne"}</td>
            <td>${item.family || "Non renseigne"}</td>
            <td>${item.genus || "Non renseigne"}</td>
            <td>${item.species || "Non renseigne"}</td>
            <td>${item.redListCategory || "Non renseigne"}</td>
        `;
        resultsBody.appendChild(row);
    });
}

function saveLastSearch(payload) {
    try {
        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({
                savedAt: new Date().toISOString(),
                params: payload.params,
                data: payload.data,
            })
        );
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
            familyInput.value = saved.params.family || "";
            speciesInput.value = saved.params.species || "";
            genusInput.value = saved.params.genus || "";
            countryInput.value = saved.params.country || "";
        }

        afficherResultats(saved.data);
        message.innerHTML = `<span class="text-muted">Resultats restaures apres rechargement.</span>`;
    } catch {
        // ignore parse errors
    }
}

async function runSearch() {
    const { family, species, genus, country, params } = getQueryParams();

    try {
        message.innerHTML = `<span class="text-primary">Recherche en cours...</span>`;
        setLoading(true);

        const url = `${API_URL}/search?${params.toString()}`;
        console.log("URL appelee :", url);

        const response = await fetch(url);
        if (!response.ok) throw new Error("Erreur API");

        const data = await response.json();
        afficherResultats(data);
        saveLastSearch({ params: { family, species, genus, country }, data });

        message.innerHTML = `<span class="text-success">Recherche terminee.</span>`;
    } catch (error) {
        console.error(error);
        message.innerHTML = `<span class="text-danger">Erreur : impossible de recuperer les donnees.</span>`;
    } finally {
        setLoading(false);
    }
}

searchBtn.addEventListener("click", runSearch);

[familyInput, speciesInput, genusInput, countryInput].forEach((input) => {
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            runSearch();
        }
    });
});

resetBtn.addEventListener("click", function () {
    familyInput.value = "";
    speciesInput.value = "";
    genusInput.value = "";
    countryInput.value = "";

    message.innerHTML = "";
    countText.textContent = "Aucune recherche lancee.";

    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch {}

    resultsBody.innerHTML = `
        <tr>
            <td colspan="9" class="text-center text-muted">
                Aucun resultat a afficher.
            </td>
        </tr>
    `;
});

exportBtn.addEventListener("click", function () {
    alert("Le fichier CSV est genere cote backend dans le dossier exports/resultats.csv.");
});

restoreLastSearch();
