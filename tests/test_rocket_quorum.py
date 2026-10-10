from __future__ import annotations

import json
from pathlib import Path
import unittest

from chimera_one.rocket import _validate_local_quorum

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "quantum001-cxp"


def valid_report():
    return {
        "schema": "sovereign-cxp-local-quorum/v1",
        "status": "CONFIRMED",
        "scope": "LOCAL_IN_PROCESS_PBFT_QUORUM",
        "digest_sha256": "8" * 64,
        "view": 0,
        "sequence": 1,
        "total_nodes": 4,
        "fault_tolerance": 1,
        "quorum_size": 3,
        "prepared_certificate": "CONFIRMED",
        "commit_certificate": "CONFIRMED",
        "commit_certificate_verified": True,
        "signer_ids": [0, 1, 2],
        "master_public_key_hex": "a" * 192,
        "certificate_commitment_sha256": "b" * 64,
        "process_independence": "UNKNOWN",
        "host_independence": "UNKNOWN",
        "network_transport": "NOT_RUN",
        "distributed_finality": "UNKNOWN",
    }


class RocketQuorumTests(unittest.TestCase):
    def test_valid_local_quorum(self):
        self.assertEqual(_validate_local_quorum(valid_report(), "8" * 64), [])

    def test_retained_sovereign_artifact_binds_real_quantum_cxp(self):
        run = json.loads((FIXTURE_ROOT / "chimera-run-v2.json").read_text(encoding="utf-8"))
        report = json.loads((FIXTURE_ROOT / "sovereign-local-quorum.json").read_text(encoding="utf-8"))
        provenance = json.loads((FIXTURE_ROOT / "sovereign-provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(_validate_local_quorum(report, run["cxp_sha256"]), [])
        self.assertEqual(report["digest_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["bound_cxp_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["producer_commit"], "93b6c0fc1bb469faca558eae5c04f793b6f485c8")
        self.assertEqual(report["certificate_commitment_sha256"], provenance["certificate_commitment_sha256"])
        self.assertEqual(report["distributed_finality"], "UNKNOWN")

    def test_wrong_cxp_digest_is_rejected(self):
        errors = _validate_local_quorum(valid_report(), "9" * 64)
        self.assertIn("sovereign_digest_binding", errors)

    def test_distributed_finality_promotion_is_rejected(self):
        report = valid_report()
        report["distributed_finality"] = "CONFIRMED"
        errors = _validate_local_quorum(report, "8" * 64)
        self.assertIn("sovereign_finality_promotion", errors)

    def test_process_independence_promotion_is_rejected(self):
        report = valid_report()
        report["process_independence"] = "CONFIRMED"
        errors = _validate_local_quorum(report, "8" * 64)
        self.assertIn("sovereign_independence_promotion", errors)


if __name__ == "__main__":
    unittest.main()
