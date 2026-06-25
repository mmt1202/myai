from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ai_code_agent import run_ai_code_agent  # noqa: E402


class AICodeAgentTests(unittest.TestCase):
    def test_agent_without_model_writes_planning_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_dir = Path(tmpdir)
            report = run_ai_code_agent(
                project_root=PROJECT_ROOT,
                task="update api_server health",
                output_dir=output_dir,
            )
            self.assertEqual(report["model"]["status"], "not_requested")
            self.assertTrue((output_dir / "workflow_manifest.json").exists())
            self.assertTrue((output_dir / "patch_plan.json").exists())
            self.assertTrue((output_dir / "patch_spec_prompt.json").exists())
            self.assertTrue((output_dir / "ai_code_agent_report.json").exists())

    def test_agent_with_patch_spec_validates_and_generates_diff(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            output_dir = Path(tmpdir)
            patch_spec = output_dir / "input_patch_spec.json"
            patch_spec.write_text(
                json.dumps(
                    {
                        "task": "update docs wording",
                        "changes": [
                            {
                                "path": "docs/p1_agent_workflow.md",
                                "find": "The agent workflow runner is the first end-to-end coding-agent orchestration layer.",
                                "replace": "The agent workflow runner is the first end-to-end coding-agent orchestration layer for safe planning.",
                                "count": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report = run_ai_code_agent(
                project_root=PROJECT_ROOT,
                task="update p1_agent_workflow docs",
                output_dir=output_dir,
                patch_spec_path=patch_spec,
            )
            self.assertEqual(report["model"]["status"], "provided_patch_spec")
            self.assertTrue(report["status"]["patch_spec_validation"]["valid"])
            self.assertTrue((output_dir / "generated.diff").exists())
            self.assertTrue((output_dir / "patch_apply_dry_run.json").exists())


if __name__ == "__main__":
    unittest.main()
