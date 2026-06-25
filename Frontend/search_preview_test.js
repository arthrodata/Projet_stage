const assert = require("assert");

function normalizeSource(value) {
    const source = String(value || "").trim();
    if (source === "combined") return "both";
    if (["gbif", "silene_expert", "inaturalist", "steli", "both"].includes(source)) return source;
    return "gbif";
}

function getPreviewRows(data, source) {
    const rows = Array.isArray(data) ? data : [];
    if (normalizeSource(source) !== "both") return rows.slice(0, 10);

    const sourceOrder = ["GBIF", "Silene Expert", "iNaturalist", "STELI"];
    const grouped = sourceOrder.map((sourceName) => rows.filter((row) => row && row.source_bdd === sourceName));
    const preview = [];
    let index = 0;

    while (preview.length < 10 && grouped.some((items) => index < items.length)) {
        grouped.forEach((items) => {
            if (preview.length < 10 && index < items.length) {
                preview.push(items[index]);
            }
        });
        index += 1;
    }

    return preview.length ? preview : rows.slice(0, 10);
}

const combinedRows = [
    ...Array.from({ length: 12 }, (_, index) => ({ source_bdd: "GBIF", species: `gbif-${index}` })),
    ...Array.from({ length: 3 }, (_, index) => ({ source_bdd: "Silene Expert", species: `silene-${index}` })),
    ...Array.from({ length: 3 }, (_, index) => ({ source_bdd: "iNaturalist", species: `inat-${index}` })),
    ...Array.from({ length: 3 }, (_, index) => ({ source_bdd: "STELI", species: `steli-${index}` })),
];

const preview = getPreviewRows(combinedRows, "both");
assert.strictEqual(preview.length, 10);
assert.deepStrictEqual(preview.slice(0, 4).map((row) => row.source_bdd), [
    "GBIF",
    "Silene Expert",
    "iNaturalist",
    "STELI",
]);
assert(preview.some((row) => row.source_bdd === "Silene Expert"));
assert(preview.some((row) => row.source_bdd === "iNaturalist"));
assert(preview.some((row) => row.source_bdd === "STELI"));

const gbifPreview = getPreviewRows(combinedRows, "gbif");
assert.strictEqual(gbifPreview.length, 10);
assert.deepStrictEqual(gbifPreview, combinedRows.slice(0, 10));
