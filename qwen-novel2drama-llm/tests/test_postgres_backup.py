from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.postgres_backup import plan_backup, plan_restore


class PostgresBackupTests(unittest.TestCase):
    def test_backup_plan_does_not_print_dsn(self) -> None:
        old = os.environ.get("DEMO_DSN")
        os.environ["DEMO_DSN"] = "configured-dsn-value"
        try:
            plan = plan_backup(output_path=Path("backup.dump"), dsn_env="DEMO_DSN")
            self.assertEqual(plan["status"], "ready")
            self.assertTrue(plan["dsn_configured"])
            self.assertNotIn("configured-dsn-value", str(plan))
            self.assertIn("$DEMO_DSN", plan["command"])
        finally:
            if old is None:
                os.environ.pop("DEMO_DSN", None)
            else:
                os.environ["DEMO_DSN"] = old

    def test_restore_plan_requires_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = plan_restore(input_path=Path(tmpdir) / "missing.dump", dsn_env="MISSING_DSN")
            self.assertEqual(plan["status"], "not_ready")


if __name__ == "__main__":
    unittest.main()
