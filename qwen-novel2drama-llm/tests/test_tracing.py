from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.tracing import append_span, finish_span, load_spans, start_span, trace_summary


class TracingTests(unittest.TestCase):
    def test_trace_span_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spans.jsonl"
            span = start_span("demo.span", attributes={"component": "demo"})
            done = finish_span(span, status="ok")
            append_span(path, done)
            loaded = load_spans(path, trace_id=span.trace_id)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["name"], "demo.span")
            self.assertEqual(trace_summary(loaded)["span_count"], 1)


if __name__ == "__main__":
    unittest.main()
