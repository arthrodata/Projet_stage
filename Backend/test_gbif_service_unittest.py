import unittest
from unittest.mock import patch

from Backend.app.services.gbif_service import search_gbif


class TestGbifSearch(unittest.TestCase):
    def test_search_adds_iucn_status(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "results": [
                        {
                            "country": "Kenya",
                            "decimalLatitude": -1.286389,
                            "decimalLongitude": 36.817223,
                            "eventDate": "2024-01-02T10:30:00",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "Felidae",
                            "genus": "Panthera",
                            "species": "Panthera leo",
                            "scientificName": "Panthera leo",
                        }
                    ],
                    "endOfRecords": True,
                }

        class FakeSession:
            trust_env = False

            def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("Backend.app.services.gbif_service.requests.Session", return_value=FakeSession()), patch(
            "Backend.app.services.gbif_service.get_iucn_enrichments",
            return_value={"Panthera leo": {"iucn_status": "VU", "iucn_lookup_status": "ok"}},
        ) as enrich:
            rows = search_gbif(export_csv=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_bdd"], "GBIF")
        self.assertEqual(rows[0]["species"], "Panthera leo")
        self.assertEqual(rows[0]["iucn_status"], "VU")
        self.assertEqual(rows[0]["status"], "VU")
        enrich.assert_called_once()

    def test_search_handles_missing_genus_column(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "results": [
                        {
                            "country": "Kenya",
                            "decimalLatitude": -1.286389,
                            "decimalLongitude": 36.817223,
                            "eventDate": "2024-01-02T10:30:00",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "Felidae",
                            "species": "Panthera leo",
                            "scientificName": "Panthera leo",
                        }
                    ],
                    "endOfRecords": True,
                }

        class FakeSession:
            trust_env = False

            def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("Backend.app.services.gbif_service.requests.Session", return_value=FakeSession()):
            rows = search_gbif(genus="Panthera", export_csv=False, include_iucn=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["species"], "Panthera leo")


if __name__ == "__main__":
    unittest.main()
