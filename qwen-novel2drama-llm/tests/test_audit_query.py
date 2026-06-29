from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.audit_query import export_audit_jsonl, query_audit_events, retention_filter


class AuditQueryTests(unittest.TestCase):
    def test_query_and_export(self) -> None:
        events = [
            {"workspace_id": "w1", "owner_id": "o1", "decision": "allowed", "created_at": "2026-06-29T00:00:00+00:00"},
            {"workspace_id": "w2", "owner_id": "o2", "decision": "denied", "created_at": "2026-06-29T01:00:00+00:00"},
        ]
        result = query_audit_events(events, workspace_id="w1")
        self.assertEqual(len(result), 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            report = export_audit_jsonl(result, Path(tmpdir) / "audit.jsonl")
            self.assertEqual(report["count"], 1)

    def test_retention_filter(self) -> None:
        events = [
            {"created_at": "2026-01-01T00:00:00+00:00"},
            {"created_at": "2026-06-29T00:00:00+00:00"},
        ]
        report = retention_filter(events, keep_since="2026-06-01T00:00:00+00:00")
        self.assertEqual(report["dropped_count"], 1)
        self.assertEqual(report["kept_count"], 1)


if __name__ == "__main__":
    unittest.main()
