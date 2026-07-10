import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Backend.app.utils import database
from fastapi import HTTPException

from Backend.app.utils.auth import (
    authenticate_user,
    create_token,
    create_user,
    decode_token,
    ensure_user_can_login,
    mark_user_activity,
    mark_user_login,
)
from Backend.app.utils.history import list_search_history, remember_search


class TestAuthHistory(unittest.TestCase):
    def test_user_token_and_personal_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.db"
            with patch.object(database, "DB_PATH", db_path), patch.object(database, "DATA_DIR", db_path.parent):
                database.init_db()

                user = create_user("test@example.com", "secret123", "Ada", "Lovelace")
                authenticated = authenticate_user("test@example.com", "secret123")
                self.assertIsNotNone(authenticated)
                self.assertEqual(authenticated["first_name"], "Ada")
                self.assertEqual(authenticated["last_name"], "Lovelace")
                self.assertFalse(authenticated["is_validated"])
                with self.assertRaises(HTTPException) as exc:
                    ensure_user_can_login(authenticated)
                self.assertEqual(exc.exception.status_code, 403)

                token = create_token(user)
                payload = decode_token(token)
                self.assertEqual(payload["sub"], user["id"])

                remember_search(
                    user,
                    source="gbif",
                    params={"source": "gbif", "genus": "Cydia"},
                    rows=[{"source_bdd": "GBIF", "species": "Cydia pomonella"}],
                )

                history = list_search_history(user)
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["params"]["genus"], "Cydia")
                self.assertEqual(history[0]["data"][0]["species"], "Cydia pomonella")

    def test_initial_admin_email_is_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "app.db"
            with (
                patch.object(database, "DB_PATH", db_path),
                patch.object(database, "DATA_DIR", db_path.parent),
                patch.dict("os.environ", {"ADMIN_EMAIL": "admin@example.com"}),
            ):
                database.init_db()

                user = create_user("admin@example.com", "secret123", "Grace", "Hopper")
                self.assertTrue(user["is_admin"])
                self.assertTrue(user["is_validated"])
                ensure_user_can_login(user)
                self.assertIsNone(user["last_login_at"])

                logged_user = mark_user_login(user["id"])
                self.assertIsNotNone(logged_user["last_login_at"])
                self.assertIsNotNone(logged_user["last_activity_at"])
                first_activity = logged_user["last_activity_at"]

                mark_user_activity(user["id"])
                active_user = authenticate_user("admin@example.com", "secret123")
                self.assertIsNotNone(active_user["last_activity_at"])
                self.assertGreaterEqual(active_user["last_activity_at"], first_activity)


if __name__ == "__main__":
    unittest.main()
