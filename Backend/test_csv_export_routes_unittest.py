import unittest
from unittest.mock import patch

from Backend.app.routes import combined, search, silene_expert


class TestCsvExportRoutes(unittest.TestCase):
    def test_silene_csv_export_keeps_iucn_status(self):
        with patch("Backend.app.routes.silene_expert.search_silene_expert_mapped") as service:
            silene_expert.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])

    def test_gbif_csv_export_keeps_iucn_status(self):
        with patch("Backend.app.routes.search.search_gbif") as service:
            search.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])

    def test_combined_csv_export_keeps_iucn_status(self):
        with patch("Backend.app.routes.combined.search_gbif_and_silene_expert") as service:
            combined.export_csv(species="Testudo hermanni")

        self.assertTrue(service.call_args.kwargs["include_iucn"])


if __name__ == "__main__":
    unittest.main()
