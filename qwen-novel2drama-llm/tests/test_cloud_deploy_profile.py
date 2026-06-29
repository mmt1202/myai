from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cloud_deploy_profile import validate_cloud_deploy_profile


class CloudDeployProfileTests(unittest.TestCase):
    def test_cloud_deploy_profile_files_exist(self) -> None:
        report = validate_cloud_deploy_profile(PROJECT_ROOT)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["missing"], [])


if __name__ == "__main__":
    unittest.main()
