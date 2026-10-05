import unittest
from pathlib import Path

from chimera_one.catalog import load_catalog
from chimera_one.plan import build_plan

ROOT = Path(__file__).resolve().parents[1]


class PlanTests(unittest.TestCase):
    def test_general_plan_is_bounded_and_evidence_aware(self):
        plan = build_plan("analyze a change", "general", load_catalog(ROOT / "capabilities" / "catalog.json"))
        ids = [step["capability"] for step in plan["steps"]]
        self.assertIn("aether.execute-allowlisted", ids)
        self.assertIn("omega.verify", ids)
        self.assertFalse(plan["policy"]["unrestricted_execution"])
        self.assertEqual(plan["claims"][0]["status"], "HYPOTHESIS")

    def test_rchain_domain_includes_adversarial_method(self):
        plan = build_plan("falsify staking claim", "rchain-audit", load_catalog(ROOT / "capabilities" / "catalog.json"))
        self.assertIn("rchain-audit.first-divergence", [s["capability"] for s in plan["steps"]])


if __name__ == "__main__":
    unittest.main()
