from __future__ import annotations

import json
from pathlib import Path
import unittest

from chimera_one.cxp_v2 import digest_run, validate_run_v2

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "quantum001-cxp"


def valid_run():
    run = {
        "schema": "chimera-run/v2",
        "cxp_version": 1,
        "run_id": "run-test-001",
        "objective": "execute bounded quantum lane",
        "domain": "quantum",
        "policy": {
            "automatic_mutation": False,
            "automatic_deployment": False,
            "unrestricted_execution": False,
            "claim_promotion_requires_evidence": True,
            "typed_commands_required": True,
            "replay_required": True,
            "quorum_required": 2,
        },
        "steps": [
            {
                "id": "quantum-execution",
                "capability": "quantum001.elevator/v1",
                "provider": "Quantum001",
                "kind": "execute",
                "depends_on": [],
                "trust": {"authority": "bounded", "network": "none", "mutation": "local-artifacts-only", "evidence": "signed-replayable"},
                "state": "CERTIFIED",
            }
        ],
        "execution": {"receipt_sha256": "1" * 64},
        "evidence": {"provider_certificate_sha256": "2" * 64},
        "verification": {"replay": "CONFIRMED"},
        "consensus": {"status": "NOT_RUN", "finality": "UNKNOWN"},
        "claims": [
            {
                "id": "claim-1",
                "statement": "bounded package is coherent",
                "status": "HYPOTHESIS",
                "assessment": {"status": "SUPPORTED", "scope": "LOCAL"},
            }
        ],
        "authority": {
            "certificate_level": "ASSURED",
            "local_execution": "CONFIRMED",
            "signed_execution": "CONFIRMED",
            "deterministic_replay": "CONFIRMED",
            "two_process_quorum": "CONFIRMED",
            "distributed_consensus": "NOT_RUN",
            "hardware_attestation": "UNKNOWN",
            "qpu_execution": "UNKNOWN",
            "external_truth": "UNKNOWN",
        },
        "certificate": {"status": "ASSURED", "provider_certificate_sha256": "2" * 64},
        "cxp_sha256": "",
    }
    run["cxp_sha256"] = digest_run(run)
    return run


class CxpV2Tests(unittest.TestCase):
    def test_valid_assured_run(self):
        report = validate_run_v2(valid_run())
        self.assertTrue(report["valid"], report)

    def test_retained_quantum001_artifact_conforms(self):
        run = json.loads((FIXTURE_ROOT / "chimera-run-v2.json").read_text(encoding="utf-8"))
        provenance = json.loads((FIXTURE_ROOT / "provenance.json").read_text(encoding="utf-8"))
        report = validate_run_v2(run)
        self.assertTrue(report["valid"], report)
        self.assertEqual(run["cxp_sha256"], provenance["cxp_sha256"])
        self.assertEqual(provenance["producer_commit"], "cadc14aa71b144107523d965419b4df75d1cfd09")
        self.assertEqual(run["execution"]["provider"], "aixaria0/Quantum001")
        self.assertEqual(run["authority"]["qpu_execution"], "UNKNOWN")

    def test_tamper_is_rejected(self):
        run = valid_run()
        run["execution"]["receipt_sha256"] = "f" * 64
        report = validate_run_v2(run)
        self.assertFalse(report["valid"])
        self.assertIn("cxp_digest", report["errors"])

    def test_repaired_digest_cannot_promote_claim(self):
        run = valid_run()
        run["claims"][0]["status"] = "TRUE"
        run["cxp_sha256"] = digest_run(run)
        report = validate_run_v2(run)
        self.assertFalse(report["valid"])
        self.assertIn("claim_promotion", report["errors"])

    def test_finalized_requires_consensus(self):
        run = valid_run()
        run["certificate"]["status"] = "FINALIZED"
        run["authority"]["certificate_level"] = "FINALIZED"
        run["cxp_sha256"] = digest_run(run)
        report = validate_run_v2(run)
        self.assertFalse(report["valid"])
        self.assertIn("finalized_without_consensus", report["errors"])

    def test_unrestricted_execution_is_rejected_even_with_repaired_digest(self):
        run = valid_run()
        run["policy"]["unrestricted_execution"] = True
        run["cxp_sha256"] = digest_run(run)
        report = validate_run_v2(run)
        self.assertFalse(report["valid"])
        self.assertIn("unrestricted_execution", report["errors"])


if __name__ == "__main__":
    unittest.main()
