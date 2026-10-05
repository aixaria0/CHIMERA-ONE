import json
import tempfile
import unittest
from pathlib import Path

from chimera_one.catalog import Capability
from chimera_one.federation import federation_report


class FederationTests(unittest.TestCase):
    def test_provider_manifest_must_agree_with_registry(self):
        cap = Capability({"id":"x.cap","provider":"X"})
        constellation = {"repositories":[{"name":"X","role":"verify","url":"https://github.com/a/X","checkout":"X"}]}
        manifest = {
            "schema":"chimera-provider/v1","repository":"a/X","role":"verify","control_plane":"aixaria0/CHIMERA-ONE","version":"1",
            "entrypoints":[{"capability":"x.cap","command":["x"],"mode":"verification","network":"none","mutation":"none"}],
            "boundaries":["bounded"]
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "X"
            root.mkdir()
            (root / "chimera.provider.json").write_text(json.dumps(manifest))
            report = federation_report(Path(tmp), constellation, [cap])
        self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
