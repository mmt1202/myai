from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))

import inference.api_server as api_server


class ModelSettingsApiServerTests(unittest.TestCase):
    def test_fastapi_handlers_set_resolve_route_and_delete_settings(self) -> None:
        old_path = os.environ.get("FOUNDATION_MODEL_SETTINGS_STORE")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                os.environ["FOUNDATION_MODEL_SETTINGS_STORE"] = str(Path(tmpdir) / "settings.json")
                set_result = api_server.model_settings_put_workspace_api("w_api_server", {"primary_model": "external.deepseek.chat", "fallback_models": ["local.qwen2_5_1_5b_instruct"]})
                self.assertEqual(set_result["status"], "ok")
                self.assertEqual(set_result["output"]["settings"]["primary"], "external.deepseek.chat")
                get_result = api_server.model_settings_get_workspace_api("w_api_server")
                self.assertEqual(get_result["output"]["settings"]["primary"], "external.deepseek.chat")
                pref = api_server.model_preferences_resolve_api({"workspace_id": "w_api_server"})
                self.assertEqual(pref["output"]["preferences"]["primary_model"], "external.deepseek.chat")
                route = api_server.model_route_with_settings_api({"workspace_id": "w_api_server", "input": [{"type": "text", "text": "hello"}], "required_capabilities": ["text.chat"]})
                self.assertEqual(route["output"]["route"]["selected_model_id"], "external.deepseek.chat")
                deleted = api_server.model_settings_delete_workspace_api("w_api_server")
                self.assertEqual(deleted["output"]["removed"]["primary"], "external.deepseek.chat")
            finally:
                if old_path is None:
                    os.environ.pop("FOUNDATION_MODEL_SETTINGS_STORE", None)
                else:
                    os.environ["FOUNDATION_MODEL_SETTINGS_STORE"] = old_path

    def test_invalid_workspace_id_returns_failed_envelope(self) -> None:
        result = api_server.model_settings_put_workspace_api("../bad", {"primary": "external.deepseek.chat"})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "invalid_model_settings_scope")


if __name__ == "__main__":
    unittest.main()
