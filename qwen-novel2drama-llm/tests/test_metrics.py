from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.metrics import MetricSample, render_prometheus, runtime_metric_samples


class MetricsTests(unittest.TestCase):
    def test_render_prometheus_escapes_labels(self) -> None:
        text = render_prometheus([MetricSample("demo_metric", 1, labels={"path": '/v1/"chat"'}, help_text="Demo metric")])
        self.assertIn("# HELP demo_metric Demo metric", text)
        self.assertIn('path="/v1/\\"chat\\""', text)
        self.assertIn("demo_metric", text)

    def test_runtime_metric_samples_include_queue_counts(self) -> None:
        samples = runtime_metric_samples(readiness={"status": "ok", "components": {"run_store": {"status": "ok"}}}, queue={"counts": {"queued": 2}, "dead_letter_count": 1}, started_at=0)
        names = {sample.name for sample in samples}
        self.assertIn("foundation_ready", names)
        self.assertIn("foundation_component_ok", names)
        self.assertIn("foundation_agent_queue_runs", names)
        self.assertIn("foundation_agent_queue_dead_letter", names)


if __name__ == "__main__":
    unittest.main()
