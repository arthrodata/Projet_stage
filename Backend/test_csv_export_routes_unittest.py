import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

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
                max_pages=None,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.search.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.search.search_gbif"
            ) as service:
                response = search.export_csv(species="Panthera leo")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_gbif_csv_export_refresh_bypasses_cached_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats.csv"
            export_file.write_text("source_bdd,species\nold,file\n", encoding="utf-8")
            signature = export_signature(
                "gbif",
                family=None,
                genus=None,
                species="Panthera leo",
                country=None,
                date_from=None,
                date_to=None,
                limit=300,
                max_pages=None,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.search.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.search.search_gbif"
            ) as service:
                service.side_effect = lambda **kwargs: Path(kwargs["export_file"]).write_text(
                    "source_bdd,species\nGBIF,Panthera leo\n",
                    encoding="utf-8",
                )
                response = search.export_csv(species="Panthera leo", refresh="1")
                written = export_file.read_text(encoding="utf-8")

        service.assert_called_once()
        self.assertEqual(response.path, str(export_file))
        self.assertIn("GBIF,Panthera leo", written)

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
                max_pages=None,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.silene_expert.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.silene_expert.search_silene_expert_mapped"
            ) as service:
                response = silene_expert.export_csv(species="Testudo hermanni")

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
                max_pages=None,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.inaturalist.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.inaturalist.search_inaturalist"
            ) as service:
                response = inaturalist.export_csv(species="Testudo hermanni")

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
                max_pages=None,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.combined.COMBINED_EXPORT_FILE", export_file), patch(
                "Backend.app.routes.combined.search_gbif_and_silene_expert"
            ) as service:
                response = combined.export_csv(species="Panthera leo")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_combined_search_updates_export_csv(self):
        rows = [
            {"source_bdd": "GBIF", "species": "Panthera leo", "country": "Kenya"},
            {"source_bdd": "iNaturalist", "species": "Panthera leo", "country": "Kenya"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_gbif_silene_inaturalist.csv"
            original = "source_bdd,species\nfull,export\n"
            export_file.write_text(original, encoding="utf-8")

            with patch("Backend.app.routes.combined.COMBINED_EXPORT_FILE", export_file), patch(
                "Backend.app.routes.combined.search_gbif_and_silene_expert",
                return_value=rows,
            ):
                returned = combined.search(species="Panthera leo")

            content = export_file.read_text(encoding="utf-8")

            self.assertEqual(returned, rows)
            self.assertNotEqual(content, original)
            self.assertIn("GBIF", content)
            self.assertIn("iNaturalist", content)

    def test_gbif_search_updates_export_csv(self):
        rows = [
            {"source_bdd": "GBIF", "species": "Panthera leo", "country": "Kenya"},
            {"source_bdd": "GBIF", "species": "Panthera pardus", "country": "Kenya"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats.csv"
            original = "source_bdd,species\nfull,export\n"
            export_file.write_text(original, encoding="utf-8")

            with patch("Backend.app.routes.search.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.search.search_gbif",
                return_value=rows,
            ):
                returned = search.search(family="Felidae")

            content = export_file.read_text(encoding="utf-8")

            self.assertEqual(returned, rows)
            self.assertNotEqual(content, original)
            self.assertIn("Panthera leo", content)
            self.assertIn("Panthera pardus", content)

    def test_silene_search_updates_export_csv(self):
        rows = [
            {"source_bdd": "Silene Expert", "species": "Cydia pomonella", "country": "France"},
            {"source_bdd": "Silene Expert", "species": "Cydia splendana", "country": "France"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_silene_expert.csv"
            original = "source_bdd,species\nfull,export\n"
            export_file.write_text(original, encoding="utf-8")

            with patch("Backend.app.routes.silene_expert.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.silene_expert.search_silene_expert_mapped",
                return_value=rows,
            ):
                returned = silene_expert.search(genus="Cydia")

            content = export_file.read_text(encoding="utf-8")

            self.assertEqual(returned, rows)
            self.assertNotEqual(content, original)
            self.assertIn("Cydia pomonella", content)
            self.assertIn("Cydia splendana", content)

    def test_inaturalist_search_updates_export_csv(self):
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
            original = "source_bdd,species\nfull,export\n"
            export_file.write_text(original, encoding="utf-8")

            with patch("Backend.app.routes.inaturalist.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.inaturalist.search_inaturalist",
                return_value=rows,
            ):
                returned = inaturalist.search(genus="Cydia", quality_grade="research")

            content = export_file.read_text(encoding="utf-8")

            self.assertEqual(returned, rows)
            self.assertNotEqual(content, original)
            self.assertIn("iNaturalist", content)
            self.assertIn("Cydia pomonella", content)


if __name__ == "__main__":
    unittest.main()
