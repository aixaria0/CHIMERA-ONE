from __future__ import annotations

import json
from pathlib import Path
import unittest

from chimera_one.rocket_full import _validate_omega, _validate_rchain

DIGEST = "8" * 64
OMEGA_DIGEST = "9" * 64
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "quantum001-cxp"


def omega_report():
    return {
        "schema": "chimera-verification-report/v2",
        "status": "LOCALLY_SUPPORTED",
        "scope": "PINNED_ARTIFACT_TRACE_EQUALITY_ONLY",
        "envelope_digest": OMEGA_DIGEST,
        "dimensions": {
            "artifact_conformance": "CONFIRMED",
            "formal_proof": "UNKNOWN",
            "implementation_binding": "UNKNOWN",
            "runtime_reproduction": "UNKNOWN",
            "independent_observation": "UNKNOWN",
            "replay": "NOT_RUN",
            "negative_control": "PASS",
            "production_reachability": "UNKNOWN",
            "finality_externality": "UNKNOWN",
        },
    }


def rchain_summary():
    return {
        "schema": "quantum-cxp-assurance-run/v1",
        "status": "PASS",
        "scope": "DETACHED_CXP_CONTRACT_REPRODUCTION_WITH_THREE_LOCAL_PROCESSES",
        "operation": "quantum-cxp/v1",
        "cxpSha256": DIGEST,
        "processIds": [101, 102, 103],
        "distinctProcesses": 3,
        "verifierActorIds": ["v1", "v2"],
        "distinctVerifiers": 2,
        "reportStatus": "PASS",
        "reportCode": "VERIFIED",
        "reviewerStatus": "PASS",
    }


class FullRocketVerifierTests(unittest.TestCase):
    def test_valid_omega_report(self):
        self.assertEqual(_validate_omega(omega_report(), expected_digest=OMEGA_DIGEST), [])

    def test_omega_independent_observation_promotion_is_rejected(self):
        report = omega_report()
        report["dimensions"]["independent_observation"] = "CONFIRMED"
        errors = _validate_omega(report, expected_digest=OMEGA_DIGEST)
        self.assertIn("omega_independent_observation_promotion", errors)

    def test_valid_rchain_summary(self):
        self.assertEqual(_validate_rchain(rchain_summary(), expected_digest=DIGEST), [])

    def test_retained_real_rchain_assurance_summary(self):
        run = json.loads((FIXTURE_ROOT / "chimera-run-v2.json").read_text(encoding="utf-8"))
        summary = json.loads(
            (FIXTURE_ROOT / "rchain-assurance-summary.json").read_text(encoding="utf-8")
        )
        provenance = json.loads(
            (FIXTURE_ROOT / "rchain-assurance-provenance.json").read_text(encoding="utf-8")
        )
        self.assertEqual(_validate_rchain(summary, expected_digest=run["cxp_sha256"]), [])
        self.assertEqual(summary["cxpSha256"], run["cxp_sha256"])
        self.assertEqual(provenance["cxp_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["producer_commit"], "9e8c808ac4b01c2f9bdbf1cefa7b44447d53cf1a")
        self.assertEqual(provenance["artifact_sha256"], "933148cd42746593050c207b34004ff0d0215a885171fb85dc5988e7c0b7200f")
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["reportCode"], "VERIFIED")
        self.assertEqual(summary["distinctProcesses"], 3)
        self.assertEqual(summary["distinctVerifiers"], 2)

    def test_rchain_digest_mismatch_is_rejected(self):
        errors = _validate_rchain(rchain_summary(), expected_digest="7" * 64)
        self.assertIn("rchain_digest", errors)

    def test_rchain_duplicate_process_identity_is_rejected(self):
        report = rchain_summary()
        report["processIds"] = [101, 101, 103]
        errors = _validate_rchain(report, expected_digest=DIGEST)
        self.assertIn("rchain_process_identity", errors)

    def test_rchain_duplicate_verifier_identity_is_rejected(self):
        report = rchain_summary()
        report["verifierActorIds"] = ["v1", "v1"]
        errors = _validate_rchain(report, expected_digest=DIGEST)
        self.assertIn("rchain_verifier_identity", errors)


if __name__ == "__main__":
    unittest.main()
