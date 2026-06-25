import csv
import time
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
        steli_rows = [
            {
                "source_bdd": "STELI",
                "country": "France",
                "coordinates": "43.3, 5.3",
                "eventDate": "2024-04-04",
                "basisOfRecord": "HUMAN_OBSERVATION",
                "datasetName": "Suivi Temporel des Libellules",
                "family": "Aeshnidae",
                "genus": "Aeshna",
                "species": "Aeshna cyanea",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "combined.csv"

            with patch("Backend.app.services.combined_service.search_gbif", return_value=gbif_rows), patch(
                "Backend.app.services.combined_service.search_silene_expert_mapped", return_value=silene_rows
            ), patch(
                "Backend.app.services.combined_service.search_inaturalist", return_value=inaturalist_rows
            ), patch(
                "Backend.app.services.combined_service.search_steli", return_value=steli_rows
            ):
                combined = search_gbif_and_silene_expert(export_file=out, export_csv=True)

            self.assertEqual(len(combined), 4)
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
                self.assertEqual(len(rows), 4)

    def test_passes_limit_to_both_sources(self):
        with patch("Backend.app.services.combined_service.search_gbif", return_value=[]) as gbif, patch(
            "Backend.app.services.combined_service.search_silene_expert_mapped", return_value=[]
        ) as silene, patch("Backend.app.services.combined_service.search_inaturalist", return_value=[]) as inaturalist, patch(
            "Backend.app.services.combined_service.search_steli", return_value=[]
        ) as steli:
            search_gbif_and_silene_expert(limit=250, quality_grade="research,needs_id", export_csv=False)

        self.assertEqual(gbif.call_args.kwargs["limit"], 250)
        self.assertEqual(silene.call_args.kwargs["limit"], 250)
        self.assertEqual(inaturalist.call_args.kwargs["limit"], 250)
        self.assertEqual(steli.call_args.kwargs["limit"], 250)
        self.assertEqual(inaturalist.call_args.kwargs["quality_grade"], "research,needs_id")
        self.assertNotIn("quality_grade", gbif.call_args.kwargs)
        self.assertNotIn("quality_grade", silene.call_args.kwargs)
        self.assertNotIn("quality_grade", steli.call_args.kwargs)

    def test_combined_enriches_iucn_once_after_merging(self):
        with patch("Backend.app.services.combined_service.search_gbif", return_value=[]) as gbif, patch(
            "Backend.app.services.combined_service.search_silene_expert_mapped", return_value=[]
        ) as silene, patch("Backend.app.services.combined_service.search_inaturalist", return_value=[]) as inaturalist, patch(
            "Backend.app.services.combined_service.search_steli", return_value=[]
        ) as steli, patch("Backend.app.services.combined_service.get_iucn_enrichments", return_value={}) as enrich:
            search_gbif_and_silene_expert(include_iucn=True, export_csv=False)

        self.assertFalse(gbif.call_args.kwargs["include_iucn"])
        self.assertFalse(silene.call_args.kwargs["include_iucn"])
        self.assertFalse(inaturalist.call_args.kwargs["include_iucn"])
        self.assertFalse(steli.call_args.kwargs["include_iucn"])
        enrich.assert_not_called()

    def test_combined_export_keeps_other_sources_when_one_source_fails(self):
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

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "combined.csv"

            with patch("Backend.app.services.combined_service.search_gbif", side_effect=RuntimeError("GBIF down")), patch(
                "Backend.app.services.combined_service.search_silene_expert_mapped", return_value=silene_rows
            ), patch("Backend.app.services.combined_service.search_inaturalist", return_value=[]), patch(
                "Backend.app.services.combined_service.search_steli", return_value=[]
            ), patch(
                "Backend.app.services.combined_service.logger.exception"
            ) as log_exception:
                combined = search_gbif_and_silene_expert(export_file=out, export_csv=True)

            self.assertEqual(len(combined), 1)
            self.assertEqual(combined[0]["source_bdd"], "Silene Expert")
            self.assertTrue(out.exists())
            log_exception.assert_called_once()

    def test_combined_search_keeps_fast_sources_when_one_source_times_out(self):
        gbif_rows = [{"source_bdd": "GBIF", "species": "Panthera leo"}]
        inaturalist_rows = [{"source_bdd": "iNaturalist", "species": "Panthera leo"}]

        def slow_silene(**kwargs):
            time.sleep(0.2)
            return [{"source_bdd": "Silene Expert", "species": "Panthera leo"}]

        with patch("Backend.app.services.combined_service.search_gbif", return_value=gbif_rows), patch(
            "Backend.app.services.combined_service.search_silene_expert_mapped",
            side_effect=slow_silene,
        ), patch(
            "Backend.app.services.combined_service.search_inaturalist",
            return_value=inaturalist_rows,
        ), patch(
            "Backend.app.services.combined_service.search_steli",
            return_value=[],
        ), patch(
            "Backend.app.services.combined_service.logger.warning"
        ) as warning:
            combined = search_gbif_and_silene_expert(
                export_csv=False,
                include_iucn=False,
                source_timeout=0.01,
            )

        self.assertEqual([row["source_bdd"] for row in combined], ["GBIF", "iNaturalist"])
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
