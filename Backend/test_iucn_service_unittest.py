import unittest
from unittest.mock import Mock, patch

from Backend.app.services import iucn_service


class TestIucnService(unittest.TestCase):
    def setUp(self):
        iucn_service._get_iucn_enrichment_cached.cache_clear()

    def test_selects_latest_global_assessment(self):
        payload = {
            "assessments": [
                {
                    "latest": True,
                    "red_list_category_code": "RE",
                    "assessment_id": 10,
                    "year_published": "2010",
                    "scopes": [{"code": "4", "description": {"en": "Mediterranean"}}],
                },
                {
                    "latest": True,
                    "red_list_category_code": "VU",
                    "assessment_id": 20,
                    "year_published": "2025",
                    "scopes": [{"code": "1", "description": {"en": "Global"}}],
                },
            ]
        }
        response = Mock(status_code=200)
        response.json.return_value = payload
        response.raise_for_status.return_value = None

        with patch.dict("os.environ", {"IUCN_TOKEN": "token"}), patch(
            "Backend.app.services.iucn_service.requests.Session.get",
            return_value=response,
        ):
            enrichment = iucn_service.get_iucn_enrichment("Panthera leo")

        self.assertEqual(enrichment["iucn_status"], "VU")
        self.assertEqual(enrichment["iucn_lookup_status"], "ok")
        self.assertEqual(enrichment["iucn_scope"], "Global")
        self.assertEqual(enrichment["iucn_assessment_id"], 20)

    def test_api_errors_are_not_not_evaluated(self):
        with patch.dict("os.environ", {"IUCN_TOKEN": "token"}), patch(
            "Backend.app.services.iucn_service.requests.Session.get",
            side_effect=iucn_service.requests.ConnectionError,
        ):
            enrichment = iucn_service.get_iucn_enrichment("Panthera leo")

        self.assertIsNone(enrichment["iucn_status"])
        self.assertEqual(enrichment["iucn_lookup_status"], "api_error")

    def test_invalid_taxon_does_not_call_iucn(self):
        with patch("Backend.app.services.iucn_service.requests.Session.get") as get:
            enrichment = iucn_service.get_iucn_enrichment("Cydia")

        get.assert_not_called()
        self.assertEqual(enrichment["iucn_lookup_status"], "invalid_species_name")


if __name__ == "__main__":
    unittest.main()
