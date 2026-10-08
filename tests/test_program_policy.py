import copy
import json
import unittest
from pathlib import Path

from chimera_one.program_policy import (AUTHORITY, ProgramPolicyError, evidence_digest, policy_digest,
                                        select_program_policy, validate_program_policy)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PIN = "sha256:a010084f89462aadd7b8e4c9e498fe54264ee69cbd77dfa70b1a78ddbcc393b9"
POLICY_PIN = "sha256:4cd4fa71c6eea86b31f76b72c0b4603a5f1a66794a569f88e1296668fe31e319"


class ProgramPolicyTests(unittest.TestCase):
    def evidence(self):
        return json.loads((ROOT / "examples/program-routing/v3/evidence.json").read_bytes())

    def test_selected_single_route_is_exactly_bound_to_saved_metrics(self):
        evidence = self.evidence()
        self.assertEqual(evidence["evidence_digest"], EVIDENCE_PIN)
        policy = select_program_policy(evidence, expected_evidence=evidence["evidence_digest"])
        self.assertEqual(policy["decision"], "SINGLE_FOUR_SAMPLE_CHECKED_PROGRAMS")
        self.assertEqual(policy["aggregate"], {"single_verified_answers": 24, "council_verified_answers": 23,
            "single_elapsed_ms": 224142, "council_elapsed_ms": 508261,
            "single_requests": 96, "council_requests": 96})
        self.assertEqual(policy["authority"], AUTHORITY)
        self.assertEqual(policy["policy_digest"], POLICY_PIN)
        self.assertEqual(policy["policy_digest"], policy_digest(policy))
        self.assertEqual(json.loads((ROOT / "examples/program-routing/v3/policy.json").read_bytes()), policy)
        result = validate_program_policy(policy, evidence, expected_evidence=evidence["evidence_digest"],
                                         expected_policy=policy["policy_digest"])
        self.assertEqual(result["fresh_inference"], "NOT_RUN")

    def test_external_evidence_pin_and_resealed_promotions_fail(self):
        evidence = self.evidence()
        with self.assertRaises(ProgramPolicyError):
            select_program_policy(evidence, expected_evidence="sha256:" + "0" * 64)
        for mutate in (lambda v: v["authority"].update(general_intelligence="CONFIRMED"),
                       lambda v: v["suites"][1]["council"].update(verified_answers=12),
                       lambda v: v["artifact"].update(artifact_id=1)):
            changed = copy.deepcopy(evidence)
            mutate(changed)
            changed["evidence_digest"] = evidence_digest(changed)
            with self.assertRaises(ProgramPolicyError):
                select_program_policy(changed, expected_evidence=evidence["evidence_digest"])

    def test_no_route_when_single_is_slower_or_less_accurate(self):
        for mutate in (lambda v: v["suites"][0]["single"].update(elapsed_ms=300000),
                       lambda v: v["suites"][1]["single"].update(verified_answers=10)):
            changed = self.evidence()
            mutate(changed)
            changed["evidence_digest"] = evidence_digest(changed)
            policy = select_program_policy(changed, expected_evidence=changed["evidence_digest"])
            self.assertEqual(policy["decision"], "NO_SELECTION")

    def test_changed_policy_cannot_validate_after_resealing(self):
        evidence = self.evidence()
        policy = select_program_policy(evidence, expected_evidence=evidence["evidence_digest"])
        changed = copy.deepcopy(policy)
        changed["decision"] = "NO_SELECTION"
        changed["policy_digest"] = policy_digest(changed)
        with self.assertRaises(ProgramPolicyError):
            validate_program_policy(changed, evidence, expected_evidence=evidence["evidence_digest"],
                                    expected_policy=changed["policy_digest"])


if __name__ == "__main__":
    unittest.main()
