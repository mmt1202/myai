from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ci_profiles import PROFILES, command_plan, import_check_command, install_command, profile_names_for, profile_report, unittest_command


class CIProfilesTests(unittest.TestCase):
    def test_default_group_contains_contracts_and_core(self) -> None:
        self.assertEqual(profile_names_for("default"), ["contracts", "core"])

    def test_optional_group_contains_non_heavy_profiles(self) -> None:
        self.assertEqual(profile_names_for("optional"), ["provider-adapter", "api-server", "local-provider-contract"])

    def test_core_profile_is_dependency_free_and_default_on_push(self) -> None:
        profile = PROFILES["core"]
        self.assertTrue(profile.default_on_push)
        self.assertEqual(profile.requirements, ("requirements/ci-core.txt",))
        self.assertIsNone(install_command(profile))
        command = unittest_command(profile) or ""
        self.assertIn("tests.test_foundation_core_services", command)
        self.assertIn("tests.test_run_store", command)
        self.assertIn("tests.test_sqlite_run_store", command)
        self.assertIn("tests.test_quota_store", command)

    def test_api_server_profile_has_api_requirements(self) -> None:
        profile = PROFILES["api-server"]
        self.assertEqual(profile.requirements, ("requirements/api-server.txt",))
        self.assertEqual(install_command(profile), "python -m pip install -r requirements/api-server.txt")
        self.assertEqual(unittest_command(profile), "python -m unittest tests.test_api_server_foundation")

    def test_local_model_imports_is_heavyweight_import_only(self) -> None:
        profile = PROFILES["local-model-imports"]
        self.assertTrue(profile.heavyweight)
        self.assertEqual(profile.tests, ())
        self.assertIn("torch", import_check_command(profile) or "")
        self.assertIn("requirements/local-model.txt", install_command(profile) or "")

    def test_command_plan_orders_install_before_tests_or_imports(self) -> None:
        api_plan = command_plan(PROFILES["api-server"])
        self.assertEqual(api_plan[0], "python -m pip install -r requirements/api-server.txt")
        self.assertEqual(api_plan[1], "python -m unittest tests.test_api_server_foundation")
        heavy_plan = command_plan(PROFILES["local-model-imports"])
        self.assertIn("requirements/local-model.txt", heavy_plan[0])
        self.assertIn("import_check=ok", heavy_plan[1])

    def test_profile_report_is_json_serializable_shape(self) -> None:
        report = profile_report("provider-adapter")
        self.assertEqual(report["selection"], "provider-adapter")
        self.assertEqual(report["profiles"][0]["name"], "provider-adapter")
        self.assertIn("commands", report["profiles"][0])

    def test_unknown_profile_raises(self) -> None:
        with self.assertRaises(KeyError):
            profile_names_for("missing")


if __name__ == "__main__":
    unittest.main()
