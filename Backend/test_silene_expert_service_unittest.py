import unittest
from unittest.mock import Mock, patch

from Backend.app.services import silene_expert_service
from Backend.app.services.silene_expert_service import search_silene_expert, search_silene_expert_mapped


class TestSileneExpertAuth(unittest.TestCase):
    def setUp(self):
        silene_expert_service._TOKEN_CACHE.token = None
        silene_expert_service._TOKEN_CACHE.exp_epoch = None

    def tearDown(self):
        silene_expert_service._TOKEN_CACHE.token = None
        silene_expert_service._TOKEN_CACHE.exp_epoch = None

    def test_manual_token_has_priority_over_login(self):
        with patch.dict(
            "os.environ",
            {
                "SILENE_EXPERT_TOKEN": "manual-token",
                "SILENE_EXPERT_LOGIN": "user",
                "SILENE_EXPERT_PASSWORD": "password",
            },
            clear=True,
        ), patch("Backend.app.services.silene_expert_service._login_and_get_token") as login:
            token = silene_expert_service._get_token()

        self.assertEqual(token, "manual-token")
        login.assert_not_called()

    def test_login_credentials_can_return_token(self):
        response = Mock(status_code=200)
        response.cookies.get.return_value = "login-token"
        response.raise_for_status.return_value = None

        session = Mock()
        session.post.return_value = response

        with patch.dict(
            "os.environ",
            {
                "SILENE_EXPERT_LOGIN": "user",
                "SILENE_EXPERT_PASSWORD": "password",
                "SILENE_EXPERT_APP_ID": "3",
            },
            clear=True,
        ), patch("Backend.app.services.silene_expert_service._session", return_value=session):
            token = silene_expert_service._get_token()

        self.assertEqual(token, "login-token")
        session.post.assert_called_once()
        self.assertIn("/api/auth/login", session.post.call_args.args[0])


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


class TestSileneExpertTokenRefresh(unittest.TestCase):
    def test_refresh_on_401_retries_request(self):
        class FakeResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise Exception(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeSession:
            def __init__(self):
                self.tokens_used = []

            def post(self, url, params=None, json=None, cookies=None, timeout=None):
                tok = (cookies or {}).get("token")
                self.tokens_used.append(tok)
                if tok == "oldtoken":
                    return FakeResponse(401, {})
                return FakeResponse(
                    200,
                    {
                        "features": [
                            {
                                "geometry": {"coordinates": [0, 0]},
                                "properties": {
                                    "observations": [
                                        {
                                            "nom_valide": "Testudo hermanni",
                                            "jdd_nom": "JDD",
                                            "date_debut": "2020-01-01",
                                            "famille": "Testudinidae",
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                )

        fake_session = FakeSession()

        with patch(
            "Backend.app.services.silene_expert_service._session",
            return_value=fake_session,
        ), patch(
            "Backend.app.services.silene_expert_service._get_token",
            return_value="oldtoken",
        ), patch(
            "Backend.app.services.silene_expert_service._force_refresh_token",
            return_value="newtoken",
        ):
            rows = search_silene_expert(payload={"limit": 1, "page": 1}, export_csv=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(fake_session.tokens_used, ["oldtoken", "newtoken"])


if __name__ == "__main__":
    unittest.main()
