from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "inference"))
sys.path.insert(0, str(PROJECT_ROOT / "services"))

from inference.model_router import route_model
from services.cost_estimator import estimate_cost_for_usage, instance_by_id
from services.token_counter import estimate_request_usage, estimate_text_tokens
from services.usage_ledger import read_events, summarize, write_event


class FoundationCoreServiceTests(unittest.TestCase):
    def load_json(self, rel_path: str) -> dict:
        return json.loads((PROJECT_ROOT / rel_path).read_text(encoding="utf-8"))

    def test_token_counter_counts_text_and_media_units(self) -> None:
        request = {
            "input": [
                {"type": "text", "text": "hello world"},
                {"type": "image", "uri": "file://a.png", "width": 1024, "height": 1024},
                {"type": "audio", "uri": "file://a.wav", "duration_ms": 2000},
            ]
        }
        usage = estimate_request_usage(request, expected_output_tokens=100)
        self.assertGreater(usage["input_tokens"], 0)
        self.assertEqual(usage["image_units"], 1.049)
        self.assertEqual(usage["audio_seconds"], 2.0)
        self.assertEqual(usage["output_tokens"], 100)

    def test_text_counter_handles_cjk(self) -> None:
        self.assertGreater(estimate_text_tokens("这是一个测试"), 1)

    def test_cost_estimator_uses_model_pricing(self) -> None:
        usage = {"input_tokens": 1000, "output_tokens": 1000, "image_units": 0, "video_seconds": 0, "audio_seconds": 0}
        model = {"id": "priced", "cost": {"input_per_1m": 1.0, "output_per_1m": 2.0}}
        cost = estimate_cost_for_usage(usage, model)
        self.assertEqual(cost["estimated"], 0.003)

    def test_model_router_selects_local_when_privacy_requires_local(self) -> None:
        instances = self.load_json("configs/model_instance_registry.json")
        policy = self.load_json("configs/model_routing_policy.json")
        request = {"route_mode": "balanced", "required_capabilities": ["text.chat"], "privacy": {"local_only": True}, "input": [{"type": "text", "text": "demo"}]}
        result = route_model(request, instances, policy=policy)
        self.assertEqual(result["selected_model_id"], "local.qwen2_5_1_5b_instruct")
        self.assertEqual(result["status"], "routed")

    def test_model_router_selects_multimodal_candidate_for_video(self) -> None:
        instances = self.load_json("configs/model_instance_registry.json")
        policy = self.load_json("configs/model_routing_policy.json")
        request = {"route_mode": "balanced", "required_capabilities": ["video.understand"], "input": [{"type": "video", "uri": "file://demo.mp4", "duration_ms": 1000}]}
        result = route_model(request, instances, policy=policy)
        self.assertEqual(result["status"], "routed")
        self.assertEqual(result["selected_model_id"], "external.gemini.multimodal")

    def test_usage_ledger_writes_and_summarizes(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "outputs") as tmpdir:
            ledger = Path(tmpdir) / "usage.jsonl"
            write_event(
                ledger,
                {
                    "request_id": "r1",
                    "model_id": "m1",
                    "provider": "local",
                    "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
                    "cost": {"estimated": 0.0},
                },
            )
            events = read_events(ledger)
            summary = summarize(events)
            self.assertEqual(summary["event_count"], 1)
            self.assertEqual(summary["total_tokens"], 5)
            self.assertIn("m1", summary["by_model"])


if __name__ == "__main__":
    unittest.main()
