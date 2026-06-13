import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import csv

from Backend.app.routes import combined, inaturalist, search, silene_expert
from Backend.app.utils.csv_export_cache import export_signature, remember_export


class TestCsvExportRoutes(unittest.TestCase):
    def test_silene_csv_export_keeps_iucn_status(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "Backend.app.routes.silene_expert.EXPORT_FILE", Path(tmp) / "silene.csv"
        ), patch("Backend.app.routes.silene_expert.search_silene_expert_mapped") as service:
            service.side_effect = lambda **kwargs: Path(kwargs["export_file"]).write_text("x", encoding="utf-8")
            silene_expert.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])

    def test_gbif_csv_export_keeps_iucn_status(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "Backend.app.routes.search.EXPORT_FILE", Path(tmp) / "gbif.csv"
        ), patch("Backend.app.routes.search.search_gbif") as service:
            service.side_effect = lambda **kwargs: Path(kwargs["export_file"]).write_text("x", encoding="utf-8")
            search.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])

    def test_combined_csv_export_keeps_iucn_status(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "Backend.app.routes.combined.COMBINED_EXPORT_FILE", Path(tmp) / "combined.csv"
        ), patch("Backend.app.routes.combined.search_gbif_and_silene_expert") as service:
            service.side_effect = lambda **kwargs: Path(kwargs["export_file"]).write_text("x", encoding="utf-8")
            combined.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])

    def test_inaturalist_csv_export_keeps_iucn_status(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "Backend.app.routes.inaturalist.EXPORT_FILE", Path(tmp) / "inat.csv"
        ), patch("Backend.app.routes.inaturalist.search_inaturalist") as service:
            service.side_effect = lambda **kwargs: Path(kwargs["export_file"]).write_text("x", encoding="utf-8")
            inaturalist.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])

    def test_gbif_csv_export_reuses_cached_file_for_same_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats.csv"
            export_file.write_text("source_bdd,species\nGBIF,Panthera leo\n", encoding="utf-8")
            signature = export_signature(
                "gbif",
                family=None,
                genus=None,
                species="Panthera leo",
                country=None,
                date_from=None,
                date_to=None,
                limit=300,
                max_pages=50,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.search.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.search.search_gbif"
            ) as service:
                response = search.export_csv(species="Panthera leo")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_gbif_csv_export_reuses_preview_file_after_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats.csv"
            export_file.write_text("source_bdd,species\nGBIF,Panthera leo\n", encoding="utf-8")
            remember_export(
                export_file,
                export_signature(
                    "gbif_preview",
                    family=None,
                    genus=None,
                    species="Panthera leo",
                    country=None,
                    date_from=None,
                    date_to=None,
                    limit=100,
                    page=1,
                ),
            )

            with patch("Backend.app.routes.search.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.search.search_gbif"
            ) as service:
                response = search.export_csv(species="Panthera leo", limit=100, preview=True)

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_silene_csv_export_reuses_cached_file_for_same_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_silene_expert.csv"
            export_file.write_text("source_bdd,species\nSilene Expert,Testudo hermanni\n", encoding="utf-8")
            signature = export_signature(
                "silene_expert",
                family=None,
                genus=None,
                species="Testudo hermanni",
                country=None,
                date_from=None,
                date_to=None,
                limit=200,
                max_pages=50,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.silene_expert.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.silene_expert.search_silene_expert_mapped"
            ) as service:
                response = silene_expert.export_csv(species="Testudo hermanni")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_silene_csv_export_reuses_preview_file_after_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_silene_expert.csv"
            export_file.write_text("source_bdd,species\nSilene Expert,Testudo hermanni\n", encoding="utf-8")
            remember_export(
                export_file,
                export_signature(
                    "silene_expert_preview",
                    family=None,
                    genus=None,
                    species="Testudo hermanni",
                    country=None,
                    date_from=None,
                    date_to=None,
                    limit=100,
                    page=1,
                ),
            )

            with patch("Backend.app.routes.silene_expert.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.silene_expert.search_silene_expert_mapped"
            ) as service:
                response = silene_expert.export_csv(species="Testudo hermanni", limit=100, preview=True)

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_inaturalist_csv_export_reuses_cached_file_for_same_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_inaturalist.csv"
            export_file.write_text("source_bdd,species\niNaturalist,Testudo hermanni\n", encoding="utf-8")
            signature = export_signature(
                "inaturalist",
                family=None,
                genus=None,
                species="Testudo hermanni",
                country=None,
                date_from=None,
                date_to=None,
                quality_grade=None,
                limit=200,
                max_pages=50,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.inaturalist.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.inaturalist.search_inaturalist"
            ) as service:
                response = inaturalist.export_csv(species="Testudo hermanni")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_inaturalist_csv_export_reuses_preview_file_after_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_inaturalist.csv"
            export_file.write_text("source_bdd,species\niNaturalist,Testudo hermanni\n", encoding="utf-8")
            remember_export(
                export_file,
                export_signature(
                    "inaturalist_preview",
                    family=None,
                    genus=None,
                    species="Testudo hermanni",
                    country=None,
                    date_from=None,
                    date_to=None,
                    quality_grade="casual",
                    limit=100,
                    page=1,
                ),
            )

            with patch("Backend.app.routes.inaturalist.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.inaturalist.search_inaturalist"
            ) as service:
                response = inaturalist.export_csv(
                    species="Testudo hermanni", quality_grade="casual", limit=100, preview=True
                )

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_combined_csv_export_reuses_cached_file_for_same_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_gbif_silene_inaturalist.csv"
            export_file.write_text("source_bdd,species\nGBIF,Panthera leo\n", encoding="utf-8")
            signature = export_signature(
                "combined",
                family=None,
                genus=None,
                species="Panthera leo",
                country=None,
                date_from=None,
                date_to=None,
                quality_grade=None,
                limit=200,
                max_pages=50,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.combined.COMBINED_EXPORT_FILE", export_file), patch(
                "Backend.app.routes.combined.search_gbif_and_silene_expert"
            ) as service:
                response = combined.export_csv(species="Panthera leo")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_combined_csv_export_reuses_preview_file_after_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_gbif_silene_inaturalist.csv"
            export_file.write_text("source_bdd,species\nGBIF,Panthera leo\n", encoding="utf-8")
            remember_export(
                export_file,
                export_signature(
                    "combined_preview",
                    family=None,
                    genus=None,
                    species="Panthera leo",
                    country=None,
                    date_from=None,
                    date_to=None,
                    quality_grade=None,
                    limit=100,
                    page=1,
                ),
            )

            with patch("Backend.app.routes.combined.COMBINED_EXPORT_FILE", export_file), patch(
                "Backend.app.routes.combined.search_gbif_and_silene_expert"
            ) as service:
                response = combined.export_csv(species="Panthera leo", limit=100, preview=True)

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_combined_search_updates_preview_csv_with_returned_rows(self):
        rows = [
            {"source_bdd": "GBIF", "species": "Panthera leo", "country": "Kenya"},
            {"source_bdd": "iNaturalist", "species": "Panthera leo", "country": "Kenya"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_gbif_silene_inaturalist.csv"
            export_file.write_text("source_bdd,species\nold,old\n", encoding="utf-8")

            with patch("Backend.app.routes.combined.COMBINED_EXPORT_FILE", export_file), patch(
                "Backend.app.routes.combined.search_gbif_and_silene_expert",
                return_value=rows,
            ):
                returned = combined.search(species="Panthera leo")

            with export_file.open("r", encoding="utf-8-sig", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))

        self.assertEqual(returned, rows)
        self.assertEqual(len(csv_rows), 2)
        self.assertEqual(csv_rows[0]["source_bdd"], "GBIF")
        self.assertEqual(csv_rows[1]["source_bdd"], "iNaturalist")

    def test_gbif_search_updates_preview_csv_with_returned_rows(self):
        rows = [
            {"source_bdd": "GBIF", "species": "Panthera leo", "country": "Kenya"},
            {"source_bdd": "GBIF", "species": "Panthera pardus", "country": "Kenya"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats.csv"

            with patch("Backend.app.routes.search.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.search.search_gbif",
                return_value=rows,
            ):
                returned = search.search(family="Felidae")

            with export_file.open("r", encoding="utf-8-sig", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))

        self.assertEqual(returned, rows)
        self.assertEqual(len(csv_rows), 2)
        self.assertEqual(csv_rows[0]["source_bdd"], "GBIF")
        self.assertEqual(csv_rows[1]["species"], "Panthera pardus")

    def test_silene_search_updates_preview_csv_with_returned_rows(self):
        rows = [
            {"source_bdd": "Silene Expert", "species": "Cydia pomonella", "country": "France"},
            {"source_bdd": "Silene Expert", "species": "Cydia splendana", "country": "France"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_silene_expert.csv"

            with patch("Backend.app.routes.silene_expert.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.silene_expert.search_silene_expert_mapped",
                return_value=rows,
            ):
                returned = silene_expert.search(genus="Cydia")

            with export_file.open("r", encoding="utf-8-sig", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))

        self.assertEqual(returned, rows)
        self.assertEqual(len(csv_rows), 2)
        self.assertEqual(csv_rows[0]["source_bdd"], "Silene Expert")
        self.assertEqual(csv_rows[1]["species"], "Cydia splendana")

    def test_inaturalist_search_updates_preview_csv_with_returned_rows(self):
        rows = [
            {
                "source_bdd": "iNaturalist",
                "species": "Cydia latiferreana",
                "country": "United States",
                "quality_grade": "research",
            },
            {
                "source_bdd": "iNaturalist",
                "species": "Cydia pomonella",
                "country": "France",
                "quality_grade": "research",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_inaturalist.csv"

            with patch("Backend.app.routes.inaturalist.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.inaturalist.search_inaturalist",
                return_value=rows,
            ):
                returned = inaturalist.search(genus="Cydia", quality_grade="research")

            with export_file.open("r", encoding="utf-8-sig", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))

        self.assertEqual(returned, rows)
        self.assertEqual(len(csv_rows), 2)
        self.assertEqual(csv_rows[0]["source_bdd"], "iNaturalist")
        self.assertEqual(csv_rows[1]["quality_grade"], "research")


if __name__ == "__main__":
    unittest.main()
