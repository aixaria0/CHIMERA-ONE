import copy
import json
import tempfile
import unittest
from pathlib import Path

from chimera_one.program_policy import (AUTHORITY, ProgramPolicyError, evidence_digest, policy_digest,
                                        select_program_policy, validate_program_policy)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PIN = "sha256:a010084f89462aadd7b8e4c9e498fe54264ee69cbd77dfa70b1a78ddbcc393b9"
POLICY_PIN = "sha256:4cd4fa71c6eea86b31f76b72c0b4603a5f1a66794a569f88e1296668fe31e319"
NATIVE = ROOT / "examples/program-routing/v3/native"


class ProgramPolicyTests(unittest.TestCase):
    def evidence(self):
        return json.loads((ROOT / "examples/program-routing/v3/evidence.json").read_bytes())

    def test_selected_single_route_is_exactly_bound_to_saved_metrics(self):
        evidence = self.evidence()
        self.assertEqual(evidence["evidence_digest"], EVIDENCE_PIN)
        policy = select_program_policy(evidence, expected_evidence=evidence["evidence_digest"], native_dir=NATIVE)
        self.assertEqual(policy["decision"], "SINGLE_FOUR_SAMPLE_CHECKED_PROGRAMS")
        self.assertEqual(policy["aggregate"], {"single_verified_answers": 24, "council_verified_answers": 23,
            "single_elapsed_ms": 224142, "council_elapsed_ms": 508261,
            "single_requests": 96, "council_requests": 96})
        self.assertEqual(policy["authority"], AUTHORITY)
        self.assertEqual(policy["policy_digest"], POLICY_PIN)
        self.assertEqual(policy["policy_digest"], policy_digest(policy))
        self.assertEqual(json.loads((ROOT / "examples/program-routing/v3/policy.json").read_bytes()), policy)
        result = validate_program_policy(policy, evidence, expected_evidence=evidence["evidence_digest"],
                                         expected_policy=policy["policy_digest"], native_dir=NATIVE)
        self.assertEqual(result["fresh_inference"], "NOT_RUN")

    def test_external_evidence_pin_and_resealed_promotions_fail(self):
        evidence = self.evidence()
        with self.assertRaises(ProgramPolicyError):
            select_program_policy(evidence, expected_evidence="sha256:" + "0" * 64, native_dir=NATIVE)
        for mutate in (lambda v: v["authority"].update(general_intelligence="CONFIRMED"),
                       lambda v: v["suites"][1]["council"].update(verified_answers=12),
                       lambda v: v["artifact"].update(artifact_id=1)):
            changed = copy.deepcopy(evidence)
            mutate(changed)
            changed["evidence_digest"] = evidence_digest(changed)
            with self.assertRaises(ProgramPolicyError):
                select_program_policy(changed, expected_evidence=evidence["evidence_digest"], native_dir=NATIVE)

    def test_resealed_native_pins_and_retained_byte_changes_fail(self):
        for mutate in (lambda v: v["artifact"].update(zip_sha256="sha256:" + "1" * 64),
                       lambda v: v["suites"][0].update(report_digest="sha256:" + "2" * 64)):
            changed = self.evidence()
            mutate(changed)
            changed["evidence_digest"] = evidence_digest(changed)
            with self.assertRaises(ProgramPolicyError):
                select_program_policy(changed, expected_evidence=changed["evidence_digest"], native_dir=NATIVE)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for source in NATIVE.iterdir():
                (target / source.name).write_bytes(source.read_bytes())
            path = target / "regression-report.json"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaises(ProgramPolicyError):
                select_program_policy(self.evidence(), expected_evidence=EVIDENCE_PIN, native_dir=target)

    def test_resealed_compact_metrics_cannot_depart_from_native_reports(self):
        for mutate in (lambda v: v["suites"][0]["single"].update(elapsed_ms=300000),
                       lambda v: v["suites"][1]["single"].update(verified_answers=10)):
            changed = self.evidence()
            mutate(changed)
            changed["evidence_digest"] = evidence_digest(changed)
            with self.assertRaises(ProgramPolicyError):
                select_program_policy(changed, expected_evidence=changed["evidence_digest"], native_dir=NATIVE)

    def test_non_object_suite_is_structurally_rejected(self):
        changed = self.evidence()
        changed["suites"] = [1, 2]
        changed["evidence_digest"] = evidence_digest(changed)
        with self.assertRaises(ProgramPolicyError):
            select_program_policy(changed, expected_evidence=changed["evidence_digest"], native_dir=NATIVE)

    def test_changed_policy_cannot_validate_after_resealing(self):
        evidence = self.evidence()
        policy = select_program_policy(evidence, expected_evidence=evidence["evidence_digest"], native_dir=NATIVE)
        changed = copy.deepcopy(policy)
        changed["decision"] = "NO_SELECTION"
        changed["policy_digest"] = policy_digest(changed)
        with self.assertRaises(ProgramPolicyError):
            validate_program_policy(changed, evidence, expected_evidence=evidence["evidence_digest"],
                                    expected_policy=changed["policy_digest"], native_dir=NATIVE)


if __name__ == "__main__":
    unittest.main()
