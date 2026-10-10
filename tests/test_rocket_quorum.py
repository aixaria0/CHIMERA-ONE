from __future__ import annotations

import json
from pathlib import Path
import unittest

from chimera_one.rocket import _validate_cluster_finality, _validate_local_quorum

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "quantum001-cxp"


def valid_local_report():
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


def valid_cluster_report():
    return {
        "schema": "sovereign-cxp-cluster-finality/v1",
        "status": "CONFIRMED",
        "scope": "LOCAL_4_PROCESS_LOOPBACK_PBFT",
        "digest_sha256": "8" * 64,
        "total_nodes": 4,
        "fault_tolerance": 1,
        "quorum_size": 3,
        "node_commit_observations": 4,
        "process_independence": "CONFIRMED",
        "network_transport": "LOOPBACK_TCP_CONFIRMED",
        "dkg": "CONFIRMED",
        "local_cluster_finality": "CONFIRMED",
        "host_independence": "UNKNOWN",
        "organizational_independence": "UNKNOWN",
        "cross_host_finality": "UNKNOWN",
        "global_finality": "UNKNOWN",
    }


class RocketQuorumTests(unittest.TestCase):
    def test_valid_local_quorum(self):
        self.assertEqual(_validate_local_quorum(valid_local_report(), "8" * 64), [])

    def test_retained_sovereign_local_artifact_binds_real_quantum_cxp(self):
        run = json.loads((FIXTURE_ROOT / "chimera-run-v2.json").read_text(encoding="utf-8"))
        report = json.loads((FIXTURE_ROOT / "sovereign-local-quorum.json").read_text(encoding="utf-8"))
        provenance = json.loads((FIXTURE_ROOT / "sovereign-provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(_validate_local_quorum(report, run["cxp_sha256"]), [])
        self.assertEqual(report["digest_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["bound_cxp_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["producer_commit"], "93b6c0fc1bb469faca558eae5c04f793b6f485c8")
        self.assertEqual(report["certificate_commitment_sha256"], provenance["certificate_commitment_sha256"])
        self.assertEqual(report["distributed_finality"], "UNKNOWN")

    def test_retained_four_process_cluster_finality_binds_real_quantum_cxp(self):
        run = json.loads((FIXTURE_ROOT / "chimera-run-v2.json").read_text(encoding="utf-8"))
        report = json.loads((FIXTURE_ROOT / "sovereign-cluster-finality.json").read_text(encoding="utf-8"))
        provenance = json.loads((FIXTURE_ROOT / "sovereign-cluster-provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(_validate_cluster_finality(report, run["cxp_sha256"]), [])
        self.assertEqual(report["digest_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["bound_cxp_sha256"], run["cxp_sha256"])
        self.assertEqual(provenance["producer_commit"], "195bbb2df945dcdabe08fc171324c58826b13c93")
        self.assertEqual(report["node_commit_observations"], 4)
        self.assertEqual(report["process_independence"], "CONFIRMED")
        self.assertEqual(report["network_transport"], "LOOPBACK_TCP_CONFIRMED")
        self.assertEqual(report["host_independence"], "UNKNOWN")
        self.assertEqual(report["global_finality"], "UNKNOWN")

    def test_wrong_cxp_digest_is_rejected(self):
        errors = _validate_cluster_finality(valid_cluster_report(), "9" * 64)
        self.assertIn("cluster_digest_binding", errors)

    def test_cross_host_finality_promotion_is_rejected(self):
        report = valid_cluster_report()
        report["cross_host_finality"] = "CONFIRMED"
        errors = _validate_cluster_finality(report, "8" * 64)
        self.assertIn("cluster_global_promotion", errors)

    def test_host_independence_promotion_is_rejected(self):
        report = valid_cluster_report()
        report["host_independence"] = "CONFIRMED"
        errors = _validate_cluster_finality(report, "8" * 64)
        self.assertIn("cluster_host_promotion", errors)

    def test_in_process_finality_promotion_is_rejected(self):
        report = valid_local_report()
        report["distributed_finality"] = "CONFIRMED"
        errors = _validate_local_quorum(report, "8" * 64)
        self.assertIn("sovereign_finality_promotion", errors)


if __name__ == "__main__":
    unittest.main()
