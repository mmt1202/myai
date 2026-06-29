from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.provider_smoke_test import ProviderSmokeConfig, load_config, run_smoke, skip_reasons


class ProviderSmokeConfigTests(unittest.TestCase):
    def clear_env(self) -> dict[str, str | None]:
        keys = [
            "FOUNDATION_PROVIDER_SMOKE_ENABLED",
            "FOUNDATION_PROVIDER_SMOKE_BASE_URL",
            "FOUNDATION_PROVIDER_SMOKE_MODEL",
            "FOUNDATION_PROVIDER_SMOKE_CREDENTIAL_ENV",
            "FOUNDATION_PROVIDER_SMOKE_TIMEOUT",
            "MODEL_API_KEY",
        ]
        old = {key: os.environ.get(key) for key in keys}
        for key in keys:
            os.environ.pop(key, None)
        return old

    def restore_env(self, old: dict[str, str | None]) -> None:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_config_skips_without_error(self) -> None:
        old = self.clear_env()
        try:
            config = ProviderSmokeConfig(enabled=False, base_url="", model="", credential_env="MODEL_API_KEY")
            self.assertIn("smoke_not_enabled", skip_reasons(config))
            result = run_smoke(config)
            self.assertEqual(result["status"], "skipped")
            self.assertIn("missing_base_url", result["skip_reasons"])
        finally:
            self.restore_env(old)

    def test_dry_run_never_requires_credential_value(self) -> None:
        old = self.clear_env()
        try:
            config = ProviderSmokeConfig(enabled=True, base_url="http://example.test/v1", model="demo", credential_env="MODEL_API_KEY")
            result = run_smoke(config, dry_run=True)
            self.assertEqual(result["status"], "dry_run")
            self.assertFalse(result["config"]["credential_configured"])
            self.assertEqual(result["request"]["model"], "demo")
        finally:
            self.restore_env(old)

    def test_load_config_reads_environment_without_provider_call(self) -> None:
        old = self.clear_env()
        try:
            os.environ["FOUNDATION_PROVIDER_SMOKE_ENABLED"] = "true"
            os.environ["FOUNDATION_PROVIDER_SMOKE_BASE_URL"] = "http://example.test/v1"
            os.environ["FOUNDATION_PROVIDER_SMOKE_MODEL"] = "demo"
            os.environ["FOUNDATION_PROVIDER_SMOKE_TIMEOUT"] = "7"
            args = argparse.Namespace(enabled=False, base_url=None, model=None, credential_env=None, timeout=None)
            config = load_config(args)
            self.assertTrue(config.enabled)
            self.assertEqual(config.base_url, "http://example.test/v1")
            self.assertEqual(config.model, "demo")
            self.assertEqual(config.timeout, 7)
        finally:
            self.restore_env(old)

    def test_public_config_reports_only_boolean_credential_state(self) -> None:
        old = self.clear_env()
        try:
            config = ProviderSmokeConfig(enabled=True, base_url="http://example.test/v1", model="demo", credential_env="MODEL_API_KEY")
            public = config.public_dict()
            self.assertIn("credential_configured", public)
            self.assertIs(public["credential_configured"], False)
        finally:
            self.restore_env(old)


if __name__ == "__main__":
    unittest.main()
