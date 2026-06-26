from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from skills.registry import SkillError, call_skill, import_entrypoint, list_skills, validate_registry


class SkillRegistryTests(unittest.TestCase):
    def load_registry(self) -> dict:
        return json.loads((PROJECT_ROOT / "configs" / "skills" / "foundation_skills.json").read_text(encoding="utf-8"))

    def test_registry_is_valid(self) -> None:
        errors = validate_registry(self.load_registry())
        self.assertEqual(errors, [])

    def test_list_active_skills_by_category(self) -> None:
        skills = list_skills(self.load_registry(), category="memory")
        ids = {skill["id"] for skill in skills}
        self.assertIn("foundation.memory_search", ids)
        self.assertIn("foundation.memory_write", ids)

    def test_list_planned_drama_skills(self) -> None:
        skills = list_skills(self.load_registry(), category="drama_specialist", include_planned=True)
        ids = {skill["id"] for skill in skills}
        self.assertIn("drama.story_reasoning", ids)
        self.assertIn("drama.visual_planning", ids)

    def test_import_entrypoint(self) -> None:
        function = import_entrypoint("services.token_counter:estimate_text_tokens")
        self.assertEqual(function("hello"), 2)

    def test_call_safe_skill(self) -> None:
        result = call_skill(
            self.load_registry(),
            "foundation.token_count",
            {"request": {"input": [{"type": "text", "text": "hello"}]}, "expected_output_tokens": 10},
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("total_tokens", result["result"])

    def test_provider_skill_requires_permission_and_approval(self) -> None:
        with self.assertRaises(SkillError):
            call_skill(self.load_registry(), "foundation.provider_generate", {"request": {}, "registry": {}})


if __name__ == "__main__":
    unittest.main()
