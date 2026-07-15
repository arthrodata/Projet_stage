import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

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
                    "quality_grade": "needs_id",
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
        self.assertEqual(rows[0]["coordinates"], "43, 5")
        self.assertEqual(rows[0]["eventDate"], "2024-05-01")
        self.assertEqual(rows[0]["family"], "Testudinidae")
        self.assertEqual(rows[0]["genus"], "Testudo")
        self.assertEqual(rows[0]["species"], "Testudo hermanni")
        self.assertEqual(rows[0]["quality_grade"], "needs_id")
        self.assertEqual(rows[0]["status"], "VU")
        self.assertEqual(rows[0]["iucn_status"], "VU")
        self.assertIn("redListCategory", rows[0])

    def test_exports_csv(self):
        payload = {
            "results": [
                {
                    "observed_on": "2024-05-01",
                    "place_guess": "France",
                    "quality_grade": "research",
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
            content = out.read_text(encoding="utf-8-sig")
            self.assertIn("quality_grade", content)
            self.assertIn("research", content)

    def test_sends_quality_grade_to_api(self):
        payload = {"results": []}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        class FakeSession:
            def __init__(self):
                self.params = None

            def get(self, *args, **kwargs):
                self.params = kwargs.get("params")
                return FakeResponse()

        session = FakeSession()
        with patch("Backend.app.services.inaturalist_service._session", return_value=session):
            search_inaturalist(species="Testudo hermanni", quality_grade="research,needs_id", export_csv=False)

        self.assertEqual(session.params["quality_grade"], "research,needs_id")

    def test_retries_transient_connection_error(self):
        payload = {
            "results": [
                {
                    "observed_on": "2024-05-01",
                    "place_guess": "France",
                    "quality_grade": "research",
                    "taxon": {"rank": "species", "name": "Testudo hermanni"},
                }
            ]
        }

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return payload

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise requests.ConnectionError("temporary disconnect")
                return FakeResponse()

        session = FakeSession()
        with patch("Backend.app.services.inaturalist_service._session", return_value=session), patch(
            "Backend.app.services.inaturalist_service.time.sleep",
            return_value=None,
        ), patch(
            "Backend.app.services.inaturalist_service.get_iucn_enrichments",
            return_value={"Testudo hermanni": {"iucn_status": "VU"}},
        ):
            rows = search_inaturalist(species="Testudo hermanni", export_csv=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(session.calls, 2)


if __name__ == "__main__":
    unittest.main()
