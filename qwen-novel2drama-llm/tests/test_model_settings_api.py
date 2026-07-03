from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

from inference.model_settings_api import delete_workspace_model_settings, get_project_model_settings, get_workspace_model_settings, list_model_settings, resolve_model_preferences_api, route_with_model_settings_api, set_project_model_settings, set_workspace_model_settings


class ModelSettingsApiTests(unittest.TestCase):
    def test_workspace_project_settings_and_route(self) -> None:
        old_path = os.environ.get("FOUNDATION_MODEL_SETTINGS_STORE")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.environ["FOUNDATION_MODEL_SETTINGS_STORE"] = str(Path(tmpdir) / "settings.json")
                workspace = set_workspace_model_settings(PROJECT_ROOT, "w_api", {"primary_model": "external.deepseek.chat", "fallback_models": ["local.qwen2_5_1_5b_instruct"]})
                self.assertEqual(workspace["settings"]["primary"], "external.deepseek.chat")
                self.assertEqual(get_workspace_model_settings(PROJECT_ROOT, "w_api")["settings"]["primary"], "external.deepseek.chat")
                project = set_project_model_settings(PROJECT_ROOT, "p_api", {"primary": "external.qwen_dashscope.omni"})
                self.assertEqual(project["settings"]["primary"], "external.qwen_dashscope.omni")
                self.assertEqual(get_project_model_settings(PROJECT_ROOT, "p_api")["settings"]["primary"], "external.qwen_dashscope.omni")
                preferences = resolve_model_preferences_api(PROJECT_ROOT, {"workspace_id": "w_api"})["preferences"]
                self.assertEqual(preferences["primary_model"], "external.deepseek.chat")
                route = route_with_model_settings_api(PROJECT_ROOT, {"project_id": "p_api", "workspace_id": "w_api", "input": [{"type": "text", "text": "hello"}], "required_capabilities": ["text.chat"]})["route"]
                self.assertEqual(route["selected_model_id"], "external.qwen_dashscope.omni")
                self.assertIn("projects", list_model_settings(PROJECT_ROOT)["settings"])
                removed = delete_workspace_model_settings(PROJECT_ROOT, "w_api")
                self.assertEqual(removed["removed"]["primary"], "external.deepseek.chat")
            finally:
                if old_path is None:
                    os.environ.pop("FOUNDATION_MODEL_SETTINGS_STORE", None)
                else:
                    os.environ["FOUNDATION_MODEL_SETTINGS_STORE"] = old_path


if __name__ == "__main__":
    unittest.main()
