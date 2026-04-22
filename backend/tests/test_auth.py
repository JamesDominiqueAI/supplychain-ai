from __future__ import annotations

import importlib
import os
import unittest

import jwt
from fastapi import HTTPException

from backend.tests.test_support import reset_fake_environment


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_fake_environment()
        os.environ["CLERK_SECRET_KEY"] = "sk_test_example"
        os.environ["CLERK_ISSUER"] = "https://example.clerk.accounts.dev"
        os.environ["ALLOW_DEV_AUTH_FALLBACK"] = "true"
        self.auth = importlib.import_module("auth")
        importlib.reload(self.auth)
        self.auth._jwks_client.cache_clear()

    def test_missing_token_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as context:
            self.auth.resolve_actor_id(None)

        self.assertEqual(context.exception.status_code, 401)

    def test_dev_token_fallback_requires_subject(self) -> None:
        token = jwt.encode({"sub": "user-123"}, "ignored", algorithm="HS256")

        actor_id = self.auth.resolve_actor_id(f"Bearer {token}")

        self.assertEqual(actor_id, "user-123")

    def test_missing_jwks_configuration_fails_closed(self) -> None:
        os.environ["CLERK_SECRET_KEY"] = ""
        os.environ["CLERK_ISSUER"] = ""
        os.environ["CLERK_JWKS_URL"] = ""
        importlib.reload(self.auth)
        self.auth._jwks_client.cache_clear()
        token = jwt.encode({"sub": "user-456"}, "ignored", algorithm="HS256")

        with self.assertRaises(HTTPException) as context:
            self.auth.resolve_actor_id(f"Bearer {token}")

        self.assertEqual(context.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
