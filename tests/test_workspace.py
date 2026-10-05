import tempfile
import unittest
from pathlib import Path

from chimera_one.workspace import inspect_workspace


class WorkspaceTests(unittest.TestCase):
    def test_missing_repository_is_explicit(self):
        constellation = {"repositories": [{"name":"x","role":"test","url":"https://github.com/example/x","checkout":"x"}]}
        with tempfile.TemporaryDirectory() as tmp:
            status = inspect_workspace(Path(tmp), constellation)[0]
        self.assertFalse(status.exists)
        self.assertFalse(status.is_git)
        self.assertIsNone(status.head)


if __name__ == "__main__":
    unittest.main()
