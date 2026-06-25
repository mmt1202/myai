from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_agent_workflow import run_agent_workflow  # noqa: E402


class AgentWorkflowTests(unittest.TestCase):
    def test_run_agent_workflow_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "agent_run"
            manifest = run_agent_workflow(PROJECT_ROOT, "update api_server health", output_dir, execute_tests=False)
            self.assertEqual(manifest["summary"]["test_status"], "planned")
            self.assertTrue((output_dir / "context_index.json").exists())
            self.assertTrue((output_dir / "code_symbols.json").exists())
            self.assertTrue((output_dir / "patch_plan.json").exists())
            self.assertTrue((output_dir / "test_plan_report.json").exists())
            self.assertTrue((output_dir / "workflow_manifest.json").exists())

    def test_workflow_manifest_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "agent_run"
            manifest = run_agent_workflow(PROJECT_ROOT, "search code symbols", output_dir, execute_tests=False)
            encoded = json.dumps(manifest, ensure_ascii=False)
            self.assertIn("workflow_manifest", encoded)


if __name__ == "__main__":
    unittest.main()
