import unittest
from pathlib import Path

from chimera_one.catalog import load_catalog

ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def test_catalog_is_valid_and_unique(self):
        caps = load_catalog(ROOT / "capabilities" / "catalog.json")
        self.assertGreaterEqual(len(caps), 10)
        self.assertEqual(len(caps), len({c.id for c in caps}))

    def test_all_constellation_providers_have_capability(self):
        providers = {c.provider for c in load_catalog(ROOT / "capabilities" / "catalog.json")}
        expected = {"RitualGraph", "aether-runtime", "CHIMERA-OMEGA", "chimera-rchain-staking-audit", "RCHAIN-COMPLIER", "Chimera-AG"}
        self.assertEqual(expected, providers)


if __name__ == "__main__":
    unittest.main()
