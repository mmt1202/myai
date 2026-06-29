from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from drama.api import drama_characters_api, drama_outline_api, drama_parse_api, drama_pipeline_api, drama_prompts_api, drama_quality_api, drama_storyboard_api


SAMPLE_NOVEL = "第一章 重逢\n林晚看见顾承，沈砚也来到现场。林晚决定反击。"


class DramaApiTests(unittest.TestCase):
    def test_step_handlers(self) -> None:
        parsed = drama_parse_api({"text": SAMPLE_NOVEL})
        self.assertEqual(parsed["status"], "ok")
        outline = drama_outline_api({"parsed": parsed["output"], "episode_count": 1})
        self.assertEqual(outline["status"], "ok")
        characters = drama_characters_api({"parsed": parsed["output"]})
        storyboard = drama_storyboard_api({"parsed": parsed["output"], "outline": outline["output"]["outline"], "character_system": characters["output"]})
        prompts = drama_prompts_api({"parsed": parsed["output"], "outline": outline["output"]["outline"], "character_system": characters["output"], "storyboard": storyboard["output"], "platforms": ["jimeng"]})
        quality = drama_quality_api({"pipeline": {"outline": outline["output"]["outline"], "character_system": characters["output"], "storyboard": storyboard["output"], "video_prompts": prompts["output"]}})
        self.assertGreater(storyboard["output"]["total_shots"], 0)
        self.assertEqual(prompts["output"]["platforms"], ["jimeng"])
        self.assertEqual(quality["status"], "ok")

    def test_pipeline_handler_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = drama_pipeline_api({"text": SAMPLE_NOVEL, "episode_count": 1, "platforms": ["jimeng"], "write_artifacts": True, "run_id": "demo"}, output_root=Path(tmpdir))
            self.assertEqual(result["status"], "ok")
            artifacts = result["output"]["artifacts"]
            self.assertTrue(Path(artifacts["files"]["full_pipeline"]).exists())


if __name__ == "__main__":
    unittest.main()
