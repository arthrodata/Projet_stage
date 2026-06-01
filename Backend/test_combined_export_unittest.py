import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Backend.app.services.combined_service import search_gbif_and_silene_expert


class TestCombinedExport(unittest.TestCase):
    def test_exports_single_csv_and_merges_rows(self):
        gbif_rows = [
            {
                "source_bdd": "GBIF",
                "country": "France",
                "coordinates": "43.0, 5.0",
                "eventDate": "2024-01-01",
                "basisOfRecord": "HUMAN_OBSERVATION",
                "datasetName": "GBIF dataset",
                "family": "Felidae",
                "genus": "Panthera",
                "species": "Panthera leo",
                "redListCategory": "VU",
                "iucn_lookup_status": "ok",
            }
        ]
        silene_rows = [
            {
                "source_bdd": "Silene Expert",
                "country": "France",
                "coordinates": "43.1, 5.1",
                "eventDate": "2024-02-02",
                "basisOfRecord": "observation",
                "datasetName": "Silene Expert",
                "family": "Felidae",
                "genus": "Panthera",
                "species": "Panthera pardus",
                "iucn_status": "EN",
                "iucn_lookup_status": "ok",
            }
        ]
        inaturalist_rows = [
            {
                "source_bdd": "iNaturalist",
                "country": "France",
                "coordinates": "43.2, 5.2",
                "eventDate": "2024-03-03",
                "basisOfRecord": "HUMAN_OBSERVATION",
                "datasetName": "iNaturalist",
                "family": "Felidae",
                "genus": "Panthera",
                "species": "Panthera onca",
                "iucn_status": "NT",
                "iucn_lookup_status": "ok",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "combined.csv"

            with patch("Backend.app.services.combined_service.search_gbif", return_value=gbif_rows), patch(
                "Backend.app.services.combined_service.search_silene_expert_mapped", return_value=silene_rows
            ), patch(
                "Backend.app.services.combined_service.search_inaturalist", return_value=inaturalist_rows
            ):
                combined = search_gbif_and_silene_expert(export_file=out, export_csv=True)

            self.assertEqual(len(combined), 3)
            self.assertTrue(out.exists())

            with out.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                self.assertIn("source_bdd", reader.fieldnames)
                self.assertIn("family", reader.fieldnames)
                self.assertIn("status", reader.fieldnames)
                self.assertNotIn("iucn_status", reader.fieldnames)
                self.assertNotIn("iucn_lookup_status", reader.fieldnames)
                self.assertNotIn("redListCategory", reader.fieldnames)
                rows = list(reader)
                self.assertEqual(len(rows), 3)

    def test_passes_limit_to_both_sources(self):
        with patch("Backend.app.services.combined_service.search_gbif", return_value=[]) as gbif, patch(
            "Backend.app.services.combined_service.search_silene_expert_mapped", return_value=[]
        ) as silene, patch("Backend.app.services.combined_service.search_inaturalist", return_value=[]) as inaturalist:
            search_gbif_and_silene_expert(limit=250, export_csv=False)

        self.assertEqual(gbif.call_args.kwargs["limit"], 250)
        self.assertEqual(silene.call_args.kwargs["limit"], 250)
        self.assertEqual(inaturalist.call_args.kwargs["limit"], 250)


if __name__ == "__main__":
    unittest.main()
