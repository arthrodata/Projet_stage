import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from Backend.app.routes import steli
from Backend.app.services.steli_service import search_steli
from Backend.app.utils.csv_export_cache import export_signature, remember_export


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.trust_env = True
        self.last_url = None
        self.last_params = None

    def get(self, url, params=None, timeout=None):
        self.last_url = url
        self.last_params = params
        return FakeResponse(self.payload)


class TestSteliService(unittest.TestCase):
    def test_uses_gbif_dataset_fallback_without_configured_endpoint(self):
        payload = {
            "results": [
                {
                    "country": "France",
                    "decimalLatitude": 43.2,
                    "decimalLongitude": 5.4,
                    "eventDate": "2024-06-01",
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "family": "Aeshnidae",
                    "genus": "Aeshna",
                    "species": "Aeshna cyanea",
                }
            ]
        }
        session = FakeSession(payload)

        with patch.dict("os.environ", {"STELI_API_URL": ""}, clear=False), patch(
            "Backend.app.services.steli_service._session",
            return_value=session,
        ):
            rows = search_steli(species="Aeshna cyanea", export_csv=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_bdd"], "STELI")
        self.assertEqual(rows[0]["datasetName"], "Suivi Temporel des Libellules")
        self.assertEqual(session.last_params["datasetKey"], "c709bf36-4964-4771-90f0-c6ba4b351620")

    def test_steli_search_adds_iucn_status(self):
        payload = {
            "results": [
                {
                    "country": "France",
                    "decimalLatitude": 43.2,
                    "decimalLongitude": 5.4,
                    "eventDate": "2024-06-01",
                    "family": "Aeshnidae",
                    "genus": "Aeshna",
                    "species": "Aeshna cyanea",
                }
            ]
        }
        session = FakeSession(payload)

        with patch.dict("os.environ", {"STELI_API_URL": ""}, clear=False), patch(
            "Backend.app.services.steli_service._session",
            return_value=session,
        ), patch(
            "Backend.app.services.steli_service.get_iucn_enrichments",
            return_value={"Aeshna cyanea": {"iucn_status": "LC", "iucn_lookup_status": "ok"}},
        ) as enrich:
            rows = search_steli(species="Aeshna cyanea", export_csv=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["iucn_status"], "LC")
        self.assertEqual(rows[0]["status"], "LC")
        enrich.assert_called_once()

    def test_maps_configured_json_endpoint_to_common_format(self):
        payload = {
            "results": [
                {
                    "country": "FR",
                    "decimalLatitude": 43.2,
                    "decimalLongitude": 5.4,
                    "eventDate": "2024-06-01",
                    "family": "Aeshnidae",
                    "genus": "Aeshna",
                    "species": "Aeshna cyanea",
                },
                {
                    "country": "FR",
                    "decimalLatitude": 44.2,
                    "decimalLongitude": 6.4,
                    "eventDate": "2020-06-01",
                    "family": "Aeshnidae",
                    "genus": "Aeshna",
                    "species": "Aeshna mixta",
                },
            ]
        }
        session = FakeSession(payload)

        with patch.dict("os.environ", {"STELI_API_URL": "https://example.test/steli"}, clear=False), patch(
            "Backend.app.services.steli_service._session",
            return_value=session,
        ):
            rows = search_steli(
                genus="Aeshna",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                export_csv=False,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_bdd"], "STELI")
        self.assertEqual(rows[0]["country"], "France")
        self.assertEqual(rows[0]["coordinates"], "43.2, 5.4")
        self.assertEqual(rows[0]["datasetName"], "Suivi Temporel des Libellules")
        self.assertEqual(rows[0]["basisOfRecord"], "Human observation / Suivi protocole")
        self.assertEqual(session.last_params["collectionCode"], "4A9DDA1F-B8FD-3E13-E053-2614A8C02B7C")

    def test_steli_csv_export_reuses_cached_file_for_same_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_steli.csv"
            export_file.write_text("source_bdd,species\nSTELI,Aeshna cyanea\n", encoding="utf-8")
            signature = export_signature(
                "steli",
                family=None,
                genus=None,
                species="Aeshna cyanea",
                country=None,
                date_from=None,
                date_to=None,
                limit=300,
                max_pages=None,
            )
            remember_export(export_file, signature)

            with patch("Backend.app.routes.steli.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.steli.search_steli"
            ) as service:
                response = steli.export_csv(species="Aeshna cyanea")

        service.assert_not_called()
        self.assertEqual(response.path, str(export_file))

    def test_steli_route_remembers_user_history(self):
        rows = [
            {
                "source_bdd": "STELI",
                "country": "France",
                "coordinates": "43.2, 5.4",
                "eventDate": "2024-06-01",
                "family": "Aeshnidae",
                "genus": "Aeshna",
                "species": "Aeshna cyanea",
                "status": "LC",
            }
        ]

        with patch("Backend.app.routes.steli.search_steli", return_value=rows), patch(
            "Backend.app.routes.steli.write_rows_export"
        ), patch("Backend.app.routes.steli.remember_search") as remember:
            data = steli.search(country="FR", limit=10, user={"id": 1})

        self.assertEqual(data, rows)
        remember.assert_called_once()
        self.assertEqual(remember.call_args.kwargs["source"], "steli")
        self.assertEqual(remember.call_args.kwargs["params"]["source"], "steli")
        self.assertEqual(remember.call_args.kwargs["params"]["country"], "FR")

    def test_steli_search_updates_export_csv(self):
        rows = [
            {
                "source_bdd": "STELI",
                "country": "France",
                "coordinates": "43.2, 5.4",
                "eventDate": "2024-06-01",
                "family": "Libellulidae",
                "genus": "Orthetrum",
                "species": "Orthetrum cancellatum",
                "status": "Non renseigne",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_steli.csv"
            original = "source_bdd,species\nold,previous\n"
            export_file.write_text(original, encoding="utf-8")

            with patch("Backend.app.routes.steli.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.steli.search_steli",
                return_value=rows,
            ):
                returned = steli.search(family="Libellulidae")

            content = export_file.read_text(encoding="utf-8-sig")

        self.assertEqual(returned, rows)
        self.assertNotEqual(content, original)
        self.assertIn("STELI", content)
        self.assertIn("Orthetrum cancellatum", content)

    def test_steli_empty_search_clears_previous_export_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_file = Path(tmp) / "resultats_steli.csv"
            original = "source_bdd,species\nSTELI,Orthetrum cancellatum\n"
            export_file.write_text(original, encoding="utf-8")

            with patch("Backend.app.routes.steli.EXPORT_FILE", export_file), patch(
                "Backend.app.routes.steli.search_steli",
                return_value=[],
            ):
                returned = steli.search(family="Tortricidae")

            content = export_file.read_text(encoding="utf-8-sig")

        self.assertEqual(returned, [])
        self.assertNotIn("Orthetrum cancellatum", content)
        self.assertIn("source_bdd", content)

    def test_steli_fetch_all_collects_multiple_gbif_pages(self):
        class PagedSession:
            def __init__(self):
                self.trust_env = True
                self.offsets = []

            def get(self, url, params=None, timeout=None):
                offset = int((params or {}).get("offset", 0))
                self.offsets.append(offset)
                species_name = "Aeshna cyanea" if offset == 0 else "Aeshna mixta"
                return FakeResponse(
                    {
                        "endOfRecords": offset > 0,
                        "results": [
                            {
                                "country": "France",
                                "decimalLatitude": 43.2 + offset,
                                "decimalLongitude": 5.4,
                                "eventDate": "2024-06-01",
                                "family": "Aeshnidae",
                                "genus": "Aeshna",
                                "species": species_name,
                            }
                        ],
                    }
                )

        session = PagedSession()
        with patch.dict("os.environ", {"STELI_API_URL": ""}, clear=False), patch(
            "Backend.app.services.steli_service._session",
            return_value=session,
        ):
            rows = search_steli(limit=1, fetch_all=True, max_pages=2, export_csv=False)

        self.assertEqual(len(rows), 2)
        self.assertEqual(session.offsets, [0, 1])


if __name__ == "__main__":
    unittest.main()
