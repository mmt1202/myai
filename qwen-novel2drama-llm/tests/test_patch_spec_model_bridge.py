from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_patch_spec_prompt import build_prompt_payload  # noqa: E402
from validate_patch_spec import validate_patch_spec  # noqa: E402


class PatchSpecModelBridgeTests(unittest.TestCase):
    def test_build_prompt_payload_contains_contract(self) -> None:
        payload = build_prompt_payload(
            task="update health",
            workflow_manifest={"summary": {"target_file_count": 1}},
            patch_plan={"target_files": [{"path": "a.py"}], "related_symbols": [], "steps": [], "safety_rules": []},
            schema={"schema_name": "patch_spec_v1"},
            chunks=[{"path": "a.py", "text": "old"}],
        )
        self.assertEqual(payload["output_contract"]["schema_name"], "patch_spec_v1")
        self.assertEqual(payload["file_chunks"][0]["path"], "a.py")

    def test_validate_patch_spec_accepts_valid_replace(self) -> None:
        spec = {"task": "demo", "changes": [{"path": "a.py", "find": "old", "replace": "new", "count": 1}]}
        plan = {"target_files": [{"path": "a.py"}]}
        self.assertEqual(validate_patch_spec(spec, plan), [])

    def test_validate_patch_spec_rejects_path_not_in_plan(self) -> None:
        spec = {"task": "demo", "changes": [{"path": "b.py", "find": "old", "replace": "new", "count": 1}]}
        plan = {"target_files": [{"path": "a.py"}]}
        errors = validate_patch_spec(spec, plan)
        self.assertTrue(any("target_files" in error for error in errors))

    def test_validate_patch_spec_requires_replace_count(self) -> None:
        spec = {"task": "demo", "changes": [{"path": "a.py", "find": "old", "replace": "new"}]}
        errors = validate_patch_spec(spec)
        self.assertTrue(any("count" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
