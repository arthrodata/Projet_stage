console.log("search.js charge");

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "biodiversity:last_search_v1";

const searchBtn = document.getElementById("searchBtn");
const resetBtn = document.getElementById("resetBtn");
const exportBtn = document.getElementById("exportBtn");

const resultsBody = document.getElementById("resultsBody");
const countText = document.getElementById("countText");
const message = document.getElementById("message");

const sourceSelect = document.getElementById("sourceSelect");

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
    const source = (sourceSelect?.value || "gbif").trim();
    const family = familyInput.value.trim();
    const species = speciesInput.value.trim();
    const genus = genusInput.value.trim();
    const country = countryInput.value.trim();

    const params = new URLSearchParams();
    if (family !== "") params.append("family", family);
    if (species !== "") params.append("species", species);
    if (genus !== "") params.append("genus", genus);
    if (country !== "") params.append("country", country);

    return { source, family, species, genus, country, params };
}

function afficherResultats(data) {
    resultsBody.innerHTML = "";

    if (!Array.isArray(data) || data.length === 0) {
        countText.textContent = "0 resultat trouve.";
        resultsBody.innerHTML = `
            <tr>
                <td colspan="10" class="text-center text-muted">
                    Aucun resultat trouve.
                </td>
            </tr>
        `;
        return;
    }

    const firstTen = data.slice(0, 10);
    countText.textContent = `${data.length} resultat(s) recupere(s). Affichage des 10 premiers.`;

    function getIucnValue(item) {
        return item?.status || item?.iucn_status || item?.redListCategory || "Non renseigne";
    }

    firstTen.forEach(function (item) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${item.source_bdd || "Non renseigne"}</td>
            <td>${item.country || "Non renseigne"}</td>
            <td>${item.coordinates || "Non renseigne"}</td>
            <td>${item.eventDate || "Non renseigne"}</td>
            <td>${item.basisOfRecord || "Non renseigne"}</td>
            <td>${item.datasetName || "Non renseigne"}</td>
            <td>${item.family || "Non renseigne"}</td>
            <td>${item.genus || "Non renseigne"}</td>
            <td>${item.species || "Non renseigne"}</td>
            <td>${getIucnValue(item)}</td>
        `;
        resultsBody.appendChild(row);
    });
}

function applyFamilyFilterClientSide(data, family) {
    const fam = (family || "").trim().toLowerCase();
    if (!fam) return data;
    if (!Array.isArray(data)) return [];
    return data.filter((item) => ((item?.family || "").toString().toLowerCase().includes(fam)));
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
            if (sourceSelect) sourceSelect.value = saved.params.source || "gbif";
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
    const { source, family, species, genus, country, params } = getQueryParams();

    try {
        message.innerHTML = `<span class="text-primary">Recherche en cours...</span>`;
        setLoading(true);

        let data = [];

        if (source === "gbif") {
            const url = `${API_URL}/search?${params.toString()}`;
            console.log("URL appelee :", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("Erreur API GBIF");
            data = await response.json();
        } else if (source === "silene_expert") {
            // Mapping : on appelle une route "search" côté backend qui applique family/genus/species/country.
            const url = `${API_URL}/silene-expert/search?${params.toString()}`;
            console.log("URL appelee :", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("Erreur API Silene Expert");
            data = await response.json();
        } else if (source === "both") {
            // Endpoint backend combiné : 1 appel + 1 seul CSV généré côté backend.
            const url = `${API_URL}/combined/search?${params.toString()}`;
            console.log("URL appelee :", url);
            const response = await fetch(url);
            if (!response.ok) throw new Error("Erreur API combinee");
            data = await response.json();
        }

        // Sécurité : appliquer le filtre famille côté client (certaines sources peuvent renvoyer
        // des familles non normalisées ou vides).
        data = applyFamilyFilterClientSide(data, family);

        afficherResultats(data);
        saveLastSearch({ params: { source, family, species, genus, country }, data });

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
    if (sourceSelect) sourceSelect.value = "gbif";
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
            <td colspan="10" class="text-center text-muted">
                Aucun resultat a afficher.
            </td>
        </tr>
    `;
});

exportBtn.addEventListener("click", function () {
    const source = (sourceSelect?.value || "gbif").trim();
    if (source === "gbif") {
        alert("CSV GBIF genere cote backend : Backend/exports/resultats.csv");
        return;
    }
    if (source === "silene_expert") {
        alert("CSV Silene Expert genere cote backend : Backend/exports/resultats_silene_expert.csv");
        return;
    }
    alert("CSV combine genere cote backend : Backend/exports/resultats_gbif_silene.csv");
});

restoreLastSearch();
