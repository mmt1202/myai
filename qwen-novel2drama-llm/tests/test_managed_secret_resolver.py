from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.managed_secret_resolver import ManagedSecretRef, managed_secret_health, resolve_managed_secret


class ManagedSecretResolverTests(unittest.TestCase):
    def test_parse_refs(self) -> None:
        ref = ManagedSecretRef.parse("aws://us-west-2/provider-key#v1")
        self.assertEqual(ref.provider, "aws")
        self.assertEqual(ref.region, "us-west-2")
        self.assertEqual(ref.name, "provider-key")
        self.assertEqual(ref.version, "v1")

    def test_env_provider_resolves(self) -> None:
        result = resolve_managed_secret("env://MODEL_KEY", env={"MODEL_KEY": "configured"})
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["value"], "configured")

    def test_external_provider_is_contract_only(self) -> None:
        result = resolve_managed_secret("vault://kv/media-provider")
        self.assertEqual(result["status"], "external_provider_required")
        self.assertEqual(result["provider"], "vault")

    def test_health_rejects_unknown_provider(self) -> None:
        report = managed_secret_health(["env://MODEL_KEY", "unknown://secret"])
        self.assertEqual(report["status"], "failed")


if __name__ == "__main__":
    unittest.main()
