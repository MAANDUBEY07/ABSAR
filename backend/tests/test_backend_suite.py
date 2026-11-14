"""Let the unchanged root unittest workflow execute the real pytest suite."""

from pathlib import Path
import subprocess
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PYTEST_TARGET = "app/tests"


class BackendSuite(unittest.TestCase):
    def test_backend_regressions(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", PYTEST_TARGET, "-q"], cwd=BACKEND_ROOT, check=False
        )
        self.assertEqual(result.returncode, 0, "Backend pytest regressions failed")


if __name__ == "__main__":
    unittest.main()
