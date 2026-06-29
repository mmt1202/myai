from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.auth import AuthError, authorize_api_key, build_auth_context, hash_api_key, required_scope_for, workspace_allowed


class AuthServiceTests(unittest.TestCase):
    def make_store(self) -> dict:
        return {
            "keys": [
                {"key_id": "admin", "sha256": hash_api_key("admin-key"), "status": "active", "owner_id": "u1", "workspaces": ["*"], "scopes": ["*"]},
                {"key_id": "readonly", "sha256": hash_api_key("read-key"), "status": "active", "owner_id": "u2", "workspaces": ["w1"], "scopes": ["foundation:read", "skills:read"]},
                {"key_id": "disabled", "sha256": hash_api_key("disabled-key"), "status": "disabled", "owner_id": "u3", "workspaces": ["*"], "scopes": ["*"]},
            ]
        }

    def test_hash_api_key_is_stable(self) -> None:
        self.assertEqual(hash_api_key("abc"), hash_api_key("abc"))
        self.assertNotEqual(hash_api_key("abc"), hash_api_key("abcd"))

    def test_required_scope_for_paths(self) -> None:
        self.assertEqual(required_scope_for("POST", "/v1/chat"), "model:invoke")
        self.assertEqual(required_scope_for("POST", "/v1/memory/write"), "memory:write")
        self.assertEqual(required_scope_for("GET", "/v1/agent/runs"), "agent:run")
        self.assertEqual(required_scope_for("GET", "/v1/agent/events"), "agent:run")
        self.assertEqual(required_scope_for("GET", "/v1/agent/status"), "agent:run")
        self.assertEqual(required_scope_for("POST", "/v1/agent/cancel"), "agent:run")
        self.assertEqual(required_scope_for("POST", "/v1/agent/retry"), "agent:run")
        self.assertEqual(required_scope_for("POST", "/v1/agent/resume"), "agent:run")
        self.assertIsNone(required_scope_for("GET", "/v1/health"))

    def test_authorize_admin_wildcard(self) -> None:
        context = authorize_api_key(self.make_store(), "admin-key", required_scope="memory:write", workspace_id="any")
        self.assertEqual(context["key_id"], "admin")

    def test_authorize_rejects_missing_scope(self) -> None:
        with self.assertRaises(AuthError):
            authorize_api_key(self.make_store(), "read-key", required_scope="memory:write", workspace_id="w1")

    def test_authorize_rejects_workspace(self) -> None:
        with self.assertRaises(AuthError):
            authorize_api_key(self.make_store(), "read-key", required_scope="foundation:read", workspace_id="w2")

    def test_authorize_rejects_disabled(self) -> None:
        with self.assertRaises(AuthError):
            authorize_api_key(self.make_store(), "disabled-key", required_scope="foundation:read")

    def test_workspace_allowed(self) -> None:
        self.assertTrue(workspace_allowed({"workspaces": ["*"]}, "x"))
        self.assertTrue(workspace_allowed({"workspaces": ["w1"]}, "w1"))
        self.assertFalse(workspace_allowed({"workspaces": ["w1"]}, "w2"))

    def test_build_auth_context_dev_anonymous(self) -> None:
        context = build_auth_context(method="POST", path="/v1/token/count", api_key=None, workspace_id=None, store=self.make_store(), auth_required=False)
        self.assertEqual(context["key_id"], "anonymous")
        self.assertEqual(context["required_scope"], "foundation:read")

    def test_build_auth_context_public_health(self) -> None:
        context = build_auth_context(method="GET", path="/v1/health", api_key=None, workspace_id=None, store=self.make_store(), auth_required=True)
        self.assertTrue(context["public"])
        self.assertEqual(context["key_id"], "anonymous")


if __name__ == "__main__":
    unittest.main()
