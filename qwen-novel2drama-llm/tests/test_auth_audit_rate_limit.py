from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.auth_audit import read_auth_events, summarize_auth_events, write_auth_event
from services.rate_limiter import RateLimitError, bucket_key, check_rate_limit, resolve_limit


class AuthAuditRateLimitTests(unittest.TestCase):
    def test_write_and_summarize_auth_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"
            write_auth_event(path, {"decision": "allowed", "key_id": "k1", "required_scope": "model:invoke", "path": "/v1/chat", "status_code": 200})
            write_auth_event(path, {"decision": "denied", "key_id": "k2", "required_scope": "memory:write", "path": "/v1/memory/write", "status_code": 403})
            events = read_auth_events(path)
            summary = summarize_auth_events(events)
            self.assertEqual(summary["event_count"], 2)
            self.assertEqual(summary["by_decision"]["allowed"], 1)
            self.assertEqual(summary["by_scope"]["model:invoke"], 1)

    def test_resolve_limit_precedence(self) -> None:
        config = {
            "default": {"enabled": True, "limit": 100, "window_seconds": 60},
            "by_scope": {"model:invoke": {"limit": 20}},
            "by_key_id": {"admin": {"limit": 500}},
        }
        self.assertEqual(resolve_limit(config, key_id="user", required_scope="model:invoke")["limit"], 20)
        self.assertEqual(resolve_limit(config, key_id="admin", required_scope="model:invoke")["limit"], 500)

    def test_bucket_key_includes_workspace(self) -> None:
        self.assertEqual(bucket_key("k1", "model:invoke", "w1"), "k1|model:invoke|w1")

    def test_check_rate_limit_allows_until_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            config = {"default": {"enabled": True, "limit": 2, "window_seconds": 60}}
            first = check_rate_limit(path, config, key_id="k1", required_scope="foundation:read", now=100)
            second = check_rate_limit(path, config, key_id="k1", required_scope="foundation:read", now=101)
            self.assertEqual(first["remaining"], 1)
            self.assertEqual(second["remaining"], 0)
            with self.assertRaises(RateLimitError):
                check_rate_limit(path, config, key_id="k1", required_scope="foundation:read", now=102)

    def test_check_rate_limit_resets_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            config = {"default": {"enabled": True, "limit": 1, "window_seconds": 10}}
            check_rate_limit(path, config, key_id="k1", required_scope="foundation:read", now=100)
            result = check_rate_limit(path, config, key_id="k1", required_scope="foundation:read", now=111)
            self.assertEqual(result["remaining"], 0)


if __name__ == "__main__":
    unittest.main()
