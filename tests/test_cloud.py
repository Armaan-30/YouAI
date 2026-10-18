"""Cloud entry point runs in its own process so desktop imports stay isolated."""
import subprocess
import sys
import unittest

class CloudTests(unittest.TestCase):
    def test_hosted_isolation_auth_and_persistence(self):
        result = subprocess.run([sys.executable, 'scripts/check_cloud.py'], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
