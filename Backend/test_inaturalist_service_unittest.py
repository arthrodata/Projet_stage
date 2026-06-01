import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Backend.app.services.inaturalist_service import search_inaturalist


class TestINaturalistSearch(unittest.TestCase):
    def test_maps_observations_to_standard_columns(self):
        payload = {
            "results": [
                {
                    "observed_on": None,
                    "observed_on_details": {"date": "2024-05-01"},
                    "place_guess": "Paris, France",
                    "place_ids": [1, 2],
                    "geojson": {"coordinates": [5.0, 43.0]},
                    "taxon": {
                        "id": 1,
                        "rank": "species",
                        "name": "Testudo hermanni",
                        "ancestors": [
                            {"rank": "family", "name": "Testudinidae"},
                            {"rank": "genus", "name": "Testudo"},
                        ],
                    },
                }
            ]
        }

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeSession:
            def get(self, url, *args, **kwargs):
                if "/places/" in url:
                    return FakeResponse({"results": [{"id": 1, "name": "France", "admin_level": 0}]})
                return FakeResponse(payload)

        with patch("Backend.app.services.inaturalist_service._session", return_value=FakeSession()), patch(
            "Backend.app.services.inaturalist_service.get_iucn_enrichments",
            return_value={"Testudo hermanni": {"iucn_status": "VU"}},
        ):
            rows = search_inaturalist(species="Testudo hermanni", export_csv=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_bdd"], "iNaturalist")
        self.assertEqual(rows[0]["country"], "France")
        self.assertEqual(rows[0]["coordinates"], "43.0, 5.0")
        self.assertEqual(rows[0]["eventDate"], "2024-05-01")
        self.assertEqual(rows[0]["family"], "Testudinidae")
        self.assertEqual(rows[0]["genus"], "Testudo")
        self.assertEqual(rows[0]["species"], "Testudo hermanni")
        self.assertEqual(rows[0]["status"], "VU")

    def test_exports_csv(self):
        payload = {
            "results": [
                {
                    "observed_on": "2024-05-01",
                    "place_guess": "France",
                    "taxon": {"rank": "species", "name": "Testudo hermanni"},
                }
            ]
        }

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp, patch(
            "Backend.app.services.inaturalist_service._session", return_value=FakeSession()
        ), patch(
            "Backend.app.services.inaturalist_service.get_iucn_enrichments",
            return_value={"Testudo hermanni": {"iucn_status": "VU"}},
        ):
            out = Path(tmp) / "inat.csv"
            search_inaturalist(species="Testudo hermanni", export_csv=True, export_file=out)

            self.assertTrue(out.exists())
            self.assertIn("iNaturalist", out.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
