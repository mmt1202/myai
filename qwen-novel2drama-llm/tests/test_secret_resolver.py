from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.secret_resolver import SecretResolutionError, parse_secret_reference, resolve_secret, secret_health


class SecretResolverTests(unittest.TestCase):
    def test_env_secret_resolution(self) -> None:
        old = os.environ.get("DEMO_SECRET")
        os.environ["DEMO_SECRET"] = "configured-value"
        try:
            self.assertEqual(resolve_secret("env:DEMO_SECRET"), "configured-value")
            ref = parse_secret_reference("env:DEMO_SECRET")
            self.assertEqual(ref.source, "env")
            self.assertTrue(ref.configured)
        finally:
            if old is None:
                os.environ.pop("DEMO_SECRET", None)
            else:
                os.environ["DEMO_SECRET"] = old

    def test_file_secret_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "secret.txt"
            path.write_text("from-file\n", encoding="utf-8")
            self.assertEqual(resolve_secret(f"file:{path}"), "from-file")

    def test_raw_secret_is_rejected_by_default(self) -> None:
        with self.assertRaises(SecretResolutionError):
            resolve_secret("plain-value")
        self.assertEqual(resolve_secret("plain-value", allow_raw=True), "plain-value")

    def test_secret_health_flags_missing_and_raw(self) -> None:
        report = secret_health({"a": "env:MISSING_DEMO_SECRET", "b": "plain-value"})
        self.assertEqual(report["status"], "degraded")
        self.assertIn("a", report["missing"])
        self.assertIn("b", report["unsafe_raw"])


if __name__ == "__main__":
    unittest.main()
