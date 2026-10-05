import tempfile
import unittest
from pathlib import Path

from chimera_one.doctor import doctor


class DoctorTests(unittest.TestCase):
    def test_missing_source_fails_closed(self):
        catalog = {"providers": [{"provider":"x","version":"1","checkout":"x","required_tools":[],"required_files":["required.txt"],"entrypoints":[]}]}
        with tempfile.TemporaryDirectory() as tmp:
            report = doctor(Path(tmp), catalog)
        self.assertFalse(report["ready"])
        self.assertFalse(report["providers"][0]["source_ready"])


if __name__ == "__main__":
    unittest.main()
