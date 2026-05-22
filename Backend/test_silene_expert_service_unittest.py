import unittest
from unittest.mock import patch

from Backend.app.services.silene_expert_service import search_silene_expert_mapped


class TestSileneExpertMappedSearch(unittest.TestCase):
    def test_species_cd_ref_has_priority_over_genus_cd_ref(self):
        rows = [
            {
                "family": "Testudinidae",
                "genus": "Testudo",
                "species": "Testudo hermanni",
                "iucn_status": "VU",
            }
        ]

        def lookup(name):
            return {"Testudo hermanni": 77433, "Testudo": 198300}.get(name)

        with patch(
            "Backend.app.services.silene_expert_service._taxhub_lookup_cd_ref",
            side_effect=lookup,
        ) as cd_ref_lookup, patch(
            "Backend.app.services.silene_expert_service.search_silene_expert",
            return_value=rows,
        ) as silene_search:
            result = search_silene_expert_mapped(
                species="Testudo hermanni",
                genus="Testudo",
                limit=2,
                export_csv=False,
            )

        self.assertEqual(result, rows)
        cd_ref_lookup.assert_called_once_with("Testudo hermanni")
        silene_search.assert_called_once_with(
            payload={"page": 1, "limit": 2, "cd_ref": 77433},
            export_csv=False,
        )


if __name__ == "__main__":
    unittest.main()
