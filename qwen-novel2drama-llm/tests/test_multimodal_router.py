from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.multimodal_router import infer_input_modalities, multimodal_route_plan, normalize_multimodal_block


class MultimodalRouterTests(unittest.TestCase):
    def test_infer_input_modalities(self) -> None:
        request = {"input": [{"type": "text", "text": "describe"}, {"type": "image", "uri": "file://a.png"}, {"type": "audio", "uri": "file://a.wav"}]}
        self.assertEqual(infer_input_modalities(request), {"text", "image", "audio"})

    def test_multimodal_route_plan_selects_matching_candidate(self) -> None:
        registry = {"instances": [{"id": "text", "input_modalities": ["text"], "output_modalities": ["text"]}, {"id": "vision", "input_modalities": ["text", "image"], "output_modalities": ["text"]}]}
        plan = multimodal_route_plan(registry, {"input": [{"type": "text", "text": "x"}, {"type": "image", "uri": "file://x.png"}]})
        self.assertEqual(plan["selected_model_id"], "vision")
        self.assertEqual(plan["candidate_count"], 1)

    def test_normalize_block(self) -> None:
        block = normalize_multimodal_block({"type": "video", "uri": "file://a.mp4", "metadata": {"fps": 24}})
        self.assertEqual(block["modality"], "video")
        self.assertEqual(block["metadata"]["fps"], 24)


if __name__ == "__main__":
    unittest.main()
