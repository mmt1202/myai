from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.model_preferences import load_model_routing_policy, resolve_model_preferences
from services.model_settings_store import ModelSettingsStore, load_policy_with_runtime_settings, model_settings_path_from_env, overlay_model_settings


class ModelSettingsStoreTests(unittest.TestCase):
    def test_set_get_delete_workspace_and_project_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ModelSettingsStore(Path(tmpdir) / "model_settings.json")
            workspace = store.set_scope("workspace", "w1", {"primary_model": "external.deepseek.chat", "fallback_models": ["local.qwen2_5_1_5b_instruct"]})
            self.assertEqual(workspace["primary"], "external.deepseek.chat")
            self.assertEqual(store.get_scope("workspace", "w1")["fallback"], ["local.qwen2_5_1_5b_instruct"])
            project = store.set_scope("project", "p1", {"primary": "external.qwen_dashscope.omni"})
            self.assertEqual(project["primary"], "external.qwen_dashscope.omni")
            removed = store.delete_scope("project", "p1")
            self.assertEqual(removed["primary"], "external.qwen_dashscope.omni")
            self.assertIsNone(store.get_scope("project", "p1"))

    def test_overlay_runtime_settings_into_policy(self) -> None:
        policy = {"global": {"default_primary_model": "model.global"}, "workspaces": {}, "projects": {}, "task_routes": {}, "guards": {}}
        settings = {"workspaces": {"w1": {"primary": "model.workspace", "fallback": []}}, "projects": {"p1": {"primary": "model.project", "fallback": []}}}
        merged = overlay_model_settings(policy, settings)
        self.assertEqual(resolve_model_preferences({"workspace_id": "w1"}, merged)["primary_model"], "model.workspace")
        self.assertEqual(resolve_model_preferences({"project_id": "p1", "workspace_id": "w1"}, merged)["primary_model"], "model.project")

    def test_load_model_routing_policy_reads_runtime_settings_from_env(self) -> None:
        old_path = os.environ.get("FOUNDATION_MODEL_SETTINGS_STORE")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                path = Path(tmpdir) / "settings.json"
                os.environ["FOUNDATION_MODEL_SETTINGS_STORE"] = str(path)
                store = ModelSettingsStore(path)
                store.set_scope("workspace", "w_env", {"primary": "external.deepseek.chat"})
                policy = load_model_routing_policy(PROJECT_ROOT / "configs" / "model_routing_policy.json")
                result = resolve_model_preferences({"workspace_id": "w_env"}, policy)
                self.assertEqual(result["primary_model"], "external.deepseek.chat")
            finally:
                if old_path is None:
                    os.environ.pop("FOUNDATION_MODEL_SETTINGS_STORE", None)
                else:
                    os.environ["FOUNDATION_MODEL_SETTINGS_STORE"] = old_path

    def test_invalid_scope_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ModelSettingsStore(Path(tmpdir) / "settings.json")
            with self.assertRaises(ValueError):
                store.set_scope("workspace", "../bad", {"primary": "x"})


if __name__ == "__main__":
    unittest.main()
