from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from call_model_for_patch_spec import (  # noqa: E402
    build_local_generate_request,
    build_openai_compatible_request,
    extract_local_generate_text,
    extract_openai_compatible_text,
    parse_json_text,
)


class ModelPatchSpecApiTests(unittest.TestCase):
    def test_build_openai_compatible_request(self) -> None:
        request = build_openai_compatible_request({"task": "demo"}, model="qwen")
        self.assertEqual(request["model"], "qwen")
        self.assertEqual(request["messages"][0]["role"], "system")
        self.assertIn("demo", request["messages"][1]["content"])

    def test_build_local_generate_request(self) -> None:
        request = build_local_generate_request({"task": "demo"})
        self.assertIn("prompt", request)
        self.assertIn("demo", request["prompt"])

    def test_extract_openai_compatible_text(self) -> None:
        response = {"choices": [{"message": {"content": "{\"task\": \"demo\", \"changes\": []}"}}]}
        self.assertIn("demo", extract_openai_compatible_text(response))

    def test_extract_local_generate_text(self) -> None:
        self.assertEqual(extract_local_generate_text({"result": "ok"}), "ok")
        self.assertEqual(extract_local_generate_text({"response": "ok"}), "ok")

    def test_parse_json_text_handles_plain_json(self) -> None:
        parsed = parse_json_text(json.dumps({"task": "demo", "changes": []}))
        self.assertEqual(parsed["task"], "demo")


if __name__ == "__main__":
    unittest.main()
