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
        self.assertEqual(profile_names_for("optional"), ["provider-adapter", "provider-smoke", "api-server", "postgres-run-store", "postgres-quota", "local-provider-contract"])

    def test_core_profile_is_dependency_free_and_default_on_push(self) -> None:
        profile = PROFILES["core"]
        self.assertTrue(profile.default_on_push)
        self.assertEqual(profile.requirements, ("requirements/ci-core.txt",))
        self.assertIsNone(install_command(profile))
        command = unittest_command(profile) or ""
        for test_name in [
            "tests.test_foundation_core_services",
            "tests.test_model_versions",
            "tests.test_model_preferences",
            "tests.test_model_settings_store",
            "tests.test_model_settings_api",
            "tests.test_model_settings_api_server",
            "tests.test_configurable_model_router",
            "tests.test_openai_responses_provider",
            "tests.test_openai_responses_smoke",
            "tests.test_api_smoke",
            "tests.test_memory_store",
            "tests.test_sqlite_memory_store",
            "tests.test_vector_memory_store",
            "tests.test_memory_backend_selection",
            "tests.test_memory_api_backend",
            "tests.test_memory_quality",
            "tests.test_quality_gate",
            "tests.test_cloud_deploy_profile",
            "tests.test_managed_secret_resolver",
            "tests.test_external_queue",
            "tests.test_billing_usage_records",
            "tests.test_provider_catalog_resilience",
            "tests.test_multimodal_router",
            "tests.test_mcp_sdk_compat",
            "tests.test_eval_runner",
            "tests.test_tracing",
            "tests.test_audit_query",
            "tests.test_deploy_profile",
            "tests.test_drama_pipeline",
            "tests.test_drama_api",
            "tests.test_media_generation",
            "tests.test_run_store",
            "tests.test_sqlite_run_store",
            "tests.test_agent_lifecycle",
            "tests.test_worker_dispatcher",
            "tests.test_postgres_migration_history",
            "tests.test_quota_store",
        ]:
            self.assertIn(test_name, command)

    def test_provider_profiles_include_openai_responses_tests(self) -> None:
        adapter_command = unittest_command(PROFILES["provider-adapter"]) or ""
        smoke_command = unittest_command(PROFILES["provider-smoke"]) or ""
        self.assertIn("tests.test_openai_responses_provider", adapter_command)
        self.assertIn("tests.test_openai_responses_smoke", smoke_command)

    def test_api_server_profile_has_api_requirements(self) -> None:
        profile = PROFILES["api-server"]
        self.assertEqual(profile.requirements, ("requirements/api-server.txt",))
        self.assertEqual(install_command(profile), "python -m pip install -r requirements/api-server.txt")
        self.assertEqual(unittest_command(profile), "python -m unittest tests.test_api_server_foundation tests.test_api_smoke tests.test_memory_api_backend tests.test_model_settings_api_server")

    def test_postgres_run_store_profile_has_optional_requirements(self) -> None:
        profile = PROFILES["postgres-run-store"]
        self.assertEqual(profile.requirements, ("requirements/postgres-run-store.txt",))
        self.assertEqual(install_command(profile), "python -m pip install -r requirements/postgres-run-store.txt")
        self.assertEqual(unittest_command(profile), "python -m unittest tests.test_postgres_run_store_contract")

    def test_postgres_quota_profile_has_optional_requirements(self) -> None:
        profile = PROFILES["postgres-quota"]
        self.assertEqual(profile.requirements, ("requirements/postgres-quota.txt",))
        self.assertEqual(install_command(profile), "python -m pip install -r requirements/postgres-quota.txt")
        self.assertEqual(unittest_command(profile), "python -m unittest tests.test_postgres_quota_store")

    def test_local_model_imports_is_heavyweight_import_only(self) -> None:
        profile = PROFILES["local-model-imports"]
        self.assertTrue(profile.heavyweight)
        self.assertEqual(profile.tests, ())
        self.assertIn("torch", import_check_command(profile) or "")
        self.assertIn("requirements/local-model.txt", install_command(profile) or "")

    def test_command_plan_orders_install_before_tests_or_imports(self) -> None:
        api_plan = command_plan(PROFILES["api-server"])
        self.assertEqual(api_plan[0], "python -m pip install -r requirements/api-server.txt")
        self.assertEqual(api_plan[1], "python -m unittest tests.test_api_server_foundation tests.test_api_smoke tests.test_memory_api_backend tests.test_model_settings_api_server")
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
