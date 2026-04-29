import subprocess
import sys
import unittest

from pixhash.constants import VERSION


class TestCLIVersion(unittest.TestCase):
    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "pixhash.cli", "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(VERSION, result.stdout)


if __name__ == "__main__":
    unittest.main()
