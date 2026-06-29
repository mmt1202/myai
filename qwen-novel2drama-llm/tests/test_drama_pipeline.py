from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from drama.characters import build_character_system
from drama.novel_parser import parse_novel, split_chapters
from drama.outline import build_episode_outline
from drama.pipeline import build_drama_pipeline, write_pipeline_artifacts
from drama.storyboard import build_storyboard, flatten_shots
from drama.video_prompts import generate_video_prompts


SAMPLE_NOVEL = """第一章 订婚夜
林晚站在宴会厅中央，顾承冷冷看着她。沈砚推门而入，所有宾客都安静下来。
林晚发现合同被人调包，她必须当场反击。
第二章 真相
顾承质问林晚，沈砚拿出证据。林晚终于明白幕后的人就在身边。
"""


class DramaPipelineTests(unittest.TestCase):
    def test_parse_novel_extracts_chapters_and_characters(self) -> None:
        chapters = split_chapters(SAMPLE_NOVEL)
        self.assertEqual(len(chapters), 2)
        parsed = parse_novel(SAMPLE_NOVEL)
        self.assertGreaterEqual(parsed["chapter_count"], 2)
        names = {item["name"] for item in parsed["characters"]}
        self.assertIn("林晚", names)

    def test_outline_character_storyboard_prompt_flow(self) -> None:
        parsed = parse_novel(SAMPLE_NOVEL)
        outline = build_episode_outline(parsed, episode_count=2)
        characters = build_character_system(parsed)
        storyboard = build_storyboard(outline, characters)
        prompts = generate_video_prompts(storyboard, characters, platforms=["jimeng"])
        self.assertEqual(outline["episode_count"], 2)
        self.assertGreater(storyboard["total_shots"], 0)
        self.assertEqual(len(prompts["items"]), storyboard["total_shots"])
        self.assertGreater(len(flatten_shots(storyboard)), 0)

    def test_full_pipeline_and_artifact_write(self) -> None:
        result = build_drama_pipeline(SAMPLE_NOVEL, episode_count=2, platforms=["jimeng"])
        self.assertEqual(result["status"], "ok")
        self.assertIn("quality", result)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = write_pipeline_artifacts(result, Path(tmpdir))
            self.assertTrue(Path(artifacts["files"]["full_pipeline"]).exists())
            self.assertTrue(Path(artifacts["files"]["video_prompts"]).exists())


if __name__ == "__main__":
    unittest.main()
