from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.model_settings import delete_runtime_model_setting, get_model_setting, load_runtime_policy, model_routing_policy_path_from_env, update_runtime_model_setting
from services.model_preferences import load_model_routing_policy, resolve_model_preferences


class ModelSettingsStoreTests(unittest.TestCase):
    def with_temp_policy_path(self):
        return tempfile.TemporaryDirectory()

    def test_runtime_policy_is_created_from_template_and_loaded_by_preferences(self) -> None:
        old_path = os.environ.get("FOUNDATION_MODEL_ROUTING_POLICY_PATH")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                path = Path(tmpdir) / "model_policy.json"
                os.environ["FOUNDATION_MODEL_ROUTING_POLICY_PATH"] = str(path)
                policy = load_runtime_policy(PROJECT_ROOT)
                self.assertTrue(path.exists())
                self.assertEqual(policy["policy_name"], "configurable_primary_model_policy_v1")
                loaded = load_model_routing_policy()
                self.assertEqual(loaded["policy_name"], policy["policy_name"])
            finally:
                if old_path is None:
                    os.environ.pop("FOUNDATION_MODEL_ROUTING_POLICY_PATH", None)
                else:
                    os.environ["FOUNDATION_MODEL_ROUTING_POLICY_PATH"] = old_path

    def test_workspace_and_project_settings_update_delete(self) -> None:
        old_path = os.environ.get("FOUNDATION_MODEL_ROUTING_POLICY_PATH")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.environ["FOUNDATION_MODEL_ROUTING_POLICY_PATH"] = str(Path(tmpdir) / "model_policy.json")
                workspace = update_runtime_model_setting(PROJECT_ROOT, "workspaces", "w1", {"primary": "external.deepseek.chat", "fallback": ["local.qwen2_5_1_5b_instruct"]})
                self.assertEqual(workspace["setting"]["primary"], "external.deepseek.chat")
                policy = load_runtime_policy(PROJECT_ROOT)
                self.assertEqual(get_model_setting(policy, "workspaces", "w1")["primary"], "external.deepseek.chat")
                preferences = resolve_model_preferences({"workspace_id": "w1"}, policy)
                self.assertEqual(preferences["primary_model"], "external.deepseek.chat")
                project = update_runtime_model_setting(PROJECT_ROOT, "projects", "p1", {"primary_model": "external.qwen_dashscope.omni", "fallback_models": ["external.deepseek.chat"]})
                self.assertEqual(project["setting"]["primary"], "external.qwen_dashscope.omni")
                deleted = delete_runtime_model_setting(PROJECT_ROOT, "projects", "p1")
                self.assertTrue(deleted["deleted"])
            finally:
                if old_path is None:
                    os.environ.pop("FOUNDATION_MODEL_ROUTING_POLICY_PATH", None)
                else:
                    os.environ["FOUNDATION_MODEL_ROUTING_POLICY_PATH"] = old_path

    def test_invalid_scope_id_is_rejected(self) -> None:
        old_path = os.environ.get("FOUNDATION_MODEL_ROUTING_POLICY_PATH")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.environ["FOUNDATION_MODEL_ROUTING_POLICY_PATH"] = str(Path(tmpdir) / "model_policy.json")
                with self.assertRaises(ValueError):
                    update_runtime_model_setting(PROJECT_ROOT, "workspaces", "../bad", {"primary": "external.deepseek.chat"})
            finally:
                if old_path is None:
                    os.environ.pop("FOUNDATION_MODEL_ROUTING_POLICY_PATH", None)
                else:
                    os.environ["FOUNDATION_MODEL_ROUTING_POLICY_PATH"] = old_path


if __name__ == "__main__":
    unittest.main()
