from __future__ import annotations

import unittest

from chimera_one.rocket import _validate_local_quorum


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
