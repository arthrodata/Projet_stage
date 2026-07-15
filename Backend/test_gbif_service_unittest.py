import unittest
from unittest.mock import patch

import requests

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

    def test_search_returns_rows_sorted_by_event_date_desc(self):
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
                            "eventDate": "2022-01-02",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "Felidae",
                            "genus": "Panthera",
                            "species": "Panthera leo",
                            "scientificName": "Panthera leo",
                        },
                        {
                            "country": "Kenya",
                            "decimalLatitude": -1.286389,
                            "decimalLongitude": 36.817223,
                            "eventDate": "2024-01-02",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "Felidae",
                            "genus": "Panthera",
                            "species": "Panthera pardus",
                            "scientificName": "Panthera pardus",
                        },
                    ],
                    "endOfRecords": True,
                }

        class FakeSession:
            trust_env = False

            def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("Backend.app.services.gbif_service.requests.Session", return_value=FakeSession()):
            rows = search_gbif(genus="Panthera", export_csv=False, include_iucn=False)

        self.assertEqual([row["eventDate"] for row in rows], ["2024-01-02", "2022-01-02"])

    def test_search_retries_transient_occurrence_failure(self):
        class FakeResponse:
            def __init__(self, status_code, payload=None):
                self.status_code = status_code
                self.payload = payload or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    response = requests.Response()
                    response.status_code = self.status_code
                    raise requests.HTTPError("temporary failure", response=response)

            def json(self):
                return self.payload

        class FakeSession:
            trust_env = False

            def __init__(self):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return FakeResponse(503)
                return FakeResponse(
                    200,
                    {
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
                    },
                )

        fake_session = FakeSession()
        with patch("Backend.app.services.gbif_service.requests.Session", return_value=fake_session), patch(
            "Backend.app.services.gbif_service.time.sleep"
        ):
            rows = search_gbif(export_csv=False, include_iucn=False)

        self.assertEqual(fake_session.calls, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_bdd"], "GBIF")

    def test_search_prefers_genus_taxon_key_over_family_taxon_key(self):
        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "results": [
                        {
                            "country": "France",
                            "decimalLatitude": 48.88081,
                            "decimalLongitude": 1.88019,
                            "eventDate": "2023-08-17",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "Tortricidae",
                            "genus": "Cydia",
                            "species": "Cydia pomonella",
                            "scientificName": "Cydia pomonella",
                        }
                    ],
                    "endOfRecords": True,
                }

        class FakeSession:
            trust_env = False

            def __init__(self):
                self.last_params = None

            def get(self, *args, **kwargs):
                self.last_params = kwargs.get("params")
                return FakeResponse()

        fake_session = FakeSession()

        def taxon_key(name, rank):
            if rank == "GENUS" and name == "Cydia":
                return 12345
            return None

        with patch("Backend.app.services.gbif_service.requests.Session", return_value=fake_session), patch(
            "Backend.app.services.gbif_service.get_gbif_taxon_key", side_effect=taxon_key
        ), patch("Backend.app.services.gbif_service.get_gbif_family_key") as family_key:
            rows = search_gbif(
                family="Tortricidae",
                genus="Cydia",
                country="FR",
                export_csv=False,
                include_iucn=False,
            )

        family_key.assert_not_called()
        self.assertEqual(fake_session.last_params["taxonKey"], 12345)
        self.assertEqual(fake_session.last_params["country"], "FR")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["genus"], "Cydia")

    def test_search_does_not_drop_genus_results_when_family_field_is_missing(self):
        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "results": [
                        {
                            "country": "France",
                            "decimalLatitude": 48.88081,
                            "decimalLongitude": 1.88019,
                            "eventDate": "2022-08-17",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "",
                            "genus": "Cydia",
                            "species": "Cydia pomonella",
                            "scientificName": "Cydia pomonella",
                        }
                    ],
                    "endOfRecords": True,
                }

        class FakeSession:
            trust_env = False

            def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("Backend.app.services.gbif_service.requests.Session", return_value=FakeSession()), patch(
            "Backend.app.services.gbif_service.get_gbif_taxon_key", return_value=12345
        ):
            rows = search_gbif(
                family="Tortricidae",
                genus="Cydia",
                export_csv=False,
                include_iucn=False,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["genus"], "Cydia")
        self.assertEqual(rows[0]["eventDate"], "2022-08-17")

    def test_search_caps_gbif_limit_to_api_page_limit(self):
        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"results": [], "endOfRecords": True}

        class FakeSession:
            trust_env = False

            def __init__(self):
                self.last_params = None

            def get(self, *args, **kwargs):
                self.last_params = kwargs.get("params")
                return FakeResponse()

        fake_session = FakeSession()
        with patch("Backend.app.services.gbif_service.requests.Session", return_value=fake_session):
            rows = search_gbif(limit=500, export_csv=False, include_iucn=False)

        self.assertEqual(rows, [])
        self.assertEqual(fake_session.last_params["limit"], 300)
        self.assertEqual(fake_session.last_params["offset"], 0)
        self.assertEqual(fake_session.last_params["orderBy"], "eventDate")
        self.assertEqual(fake_session.last_params["order"], "desc")

    def test_search_retries_occurrence_timeout(self):
        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "results": [
                        {
                            "country": "France",
                            "decimalLatitude": 48.88081,
                            "decimalLongitude": 1.88019,
                            "eventDate": "2023-08-17",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "datasetName": "GBIF dataset",
                            "family": "Tortricidae",
                            "genus": "Cydia",
                            "species": "Cydia pomonella",
                            "scientificName": "Cydia pomonella",
                        }
                    ],
                    "endOfRecords": True,
                }

        class FakeSession:
            trust_env = False

            def __init__(self):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise requests.ReadTimeout("GBIF timeout")
                return FakeResponse()

        fake_session = FakeSession()
        with patch("Backend.app.services.gbif_service.requests.Session", return_value=fake_session), patch(
            "Backend.app.services.gbif_service.time.sleep"
        ):
            rows = search_gbif(export_csv=False, include_iucn=False)

        self.assertEqual(fake_session.calls, 2)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
