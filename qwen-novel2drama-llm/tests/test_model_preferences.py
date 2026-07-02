from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.model_preferences import infer_task_type, resolve_model_preferences


POLICY = {
    "policy_name": "test_policy",
    "global": {
        "default_primary_model": "model.global",
        "fallback_models": ["model.fallback"],
        "private_models": ["model.local"],
    },
    "task_routes": {
        "coding": {"primary": "model.code", "fallback": ["model.code.backup"]},
        "drama": {"primary": "model.drama", "fallback": ["model.drama.backup"]},
    },
    "workspaces": {"w1": {"primary": "model.workspace", "fallback": ["model.workspace.backup"]}},
    "projects": {"p1": {"primary": "model.project", "fallback": ["model.project.backup"]}},
    "guards": {"allow_request_override": True, "allow_workspace_override": True, "allow_project_override": True, "privacy_local_only_forces_private_models": True},
}


class ModelPreferencesTests(unittest.TestCase):
    def test_priority_request_project_workspace_task_global(self) -> None:
        request = {"model_id": "model.request", "project_id": "p1", "workspace_id": "w1", "task_type": "coding"}
        result = resolve_model_preferences(request, POLICY)
        self.assertEqual(result["primary_model"], "model.request")
        self.assertEqual(result["policy_hits"][0], "request_primary")
        project = resolve_model_preferences({"project_id": "p1", "workspace_id": "w1", "task_type": "coding"}, POLICY)
        self.assertEqual(project["primary_model"], "model.project")
        workspace = resolve_model_preferences({"workspace_id": "w1", "task_type": "coding"}, POLICY)
        self.assertEqual(workspace["primary_model"], "model.workspace")
        task = resolve_model_preferences({"task_type": "coding"}, POLICY)
        self.assertEqual(task["primary_model"], "model.code")
        global_default = resolve_model_preferences({}, POLICY)
        self.assertEqual(global_default["primary_model"], "model.global")

    def test_privacy_guard_forces_private_models(self) -> None:
        result = resolve_model_preferences({"model_id": "model.request", "privacy": {"local_only": True}}, POLICY)
        self.assertEqual(result["primary_model"], "model.local")
        self.assertIn("privacy_guard_private_models", result["policy_hits"])

    def test_env_primary_and_fallback(self) -> None:
        old_primary = os.environ.get("FOUNDATION_PRIMARY_MODEL")
        old_fallback = os.environ.get("FOUNDATION_FALLBACK_MODELS")
        try:
            os.environ["FOUNDATION_PRIMARY_MODEL"] = "model.env"
            os.environ["FOUNDATION_FALLBACK_MODELS"] = "model.env.backup"
            result = resolve_model_preferences({}, POLICY)
            self.assertEqual(result["primary_model"], "model.env")
            self.assertIn("model.env.backup", result["fallback_models"])
        finally:
            if old_primary is None:
                os.environ.pop("FOUNDATION_PRIMARY_MODEL", None)
            else:
                os.environ["FOUNDATION_PRIMARY_MODEL"] = old_primary
            if old_fallback is None:
                os.environ.pop("FOUNDATION_FALLBACK_MODELS", None)
            else:
                os.environ["FOUNDATION_FALLBACK_MODELS"] = old_fallback

    def test_task_inference(self) -> None:
        self.assertEqual(infer_task_type({"route_mode": "code_specialist"}), "coding")
        self.assertEqual(infer_task_type({"route_mode": "drama_specialist"}), "drama")
        self.assertEqual(infer_task_type({"privacy": {"local_only": True}}), "private")
        self.assertEqual(infer_task_type({"required_capabilities": ["vision.understand"]}), "multimodal")


if __name__ == "__main__":
    unittest.main()
