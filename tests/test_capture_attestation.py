"""Real OpenSSL signatures on retained evidence and deliberately changed local fixtures."""
from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chimera_one import capture_attestation as att
from chimera_one import offline_review as review

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PIN = "sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2"
SIGNER = "test-vector-reviewer"
# Public RFC 8032 section 7.1 test vectors, NEVER production secrets or authority.
TEST_SEED = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
TEST_PUBLIC = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
OTHER_SEED = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
OTHER_PUBLIC = "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
KEY_PIN = "sha256:21fe31dfa154a261626bf854046fd2271b7bed4b6abe45aa58877ef47f9721b9"


def test_key(path: Path, seed: str = TEST_SEED) -> None:
    der = bytes.fromhex("302e020100300506032b657004220420" + seed)
    path.write_bytes(b"-----BEGIN PRIVATE KEY-----\n" + base64.b64encode(der)
                     + b"\n-----END PRIVATE KEY-----\n")
    path.chmod(0o600)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class CaptureAttestationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="one-owned-attestation-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.capture = self.root / "capture"
        shutil.copytree(ROOT / "examples/offline-review/replay", self.capture)
        self.key = self.root / "test-only.pem"
        test_key(self.key)
        self.output = self.root / "attestation.json"
        self.before = {p.relative_to(self.capture).as_posix(): p.read_bytes()
                       for p in self.capture.rglob("*") if p.is_file()}

    def sign(self, **overrides):
        arguments = dict(root=self.capture, expected_receipt=CAPTURE_PIN,
                         private_key=self.key, signer_id=SIGNER, expected_key=KEY_PIN,
                         output=self.output)
        arguments.update(overrides)
        return att.attest_capture(**arguments)

    def verify(self, **overrides):
        arguments = dict(root=self.capture, attestation=self.output,
                         expected_receipt=CAPTURE_PIN, expected_key=KEY_PIN,
                         expected_signer=SIGNER)
        arguments.update(overrides)
        return att.verify_capture_attestation(**arguments)

    def mutate_attestation(self, value):
        value["attestation_digest"] = att.attestation_digest(value)
        write_json(self.output, value)

    def rehash_receipt(self, receipt):
        receipt["receipt_digest"] = review.receipt_digest(receipt)
        write_json(self.capture / "receipt.json", receipt)
        return receipt["receipt_digest"]

    def test_real_signature_preserves_captured_bytes_and_unknown_dimensions(self):
        with patch.object(review, "review_aether_history", side_effect=AssertionError("no provider rerun")):
            created = self.sign()
            checked = self.verify()
        self.assertEqual(created["status"], "SIGNED_NOT_AUTHORIZED")
        self.assertEqual(checked["status"], "CONFIRMED")
        self.assertEqual(checked["signature_integrity"], "CONFIRMED")
        self.assertEqual(checked["policy_authorization"], "NOT_ASSESSED")
        self.assertEqual(checked["capture_validation"]["provider_outcome"], "CONFIRMED")
        for field in ("independent_observation", "process_independence", "source_build_binding",
                      "signer_identity", "freshness", "key_revocation"):
            self.assertEqual(checked[field], "UNKNOWN")
        self.assertEqual(checked["provider_execution_reproduced"], "NOT_RUN")
        self.assertEqual(checked["general_claim_verdict"], "NOT_ASSESSED")
        self.assertEqual(self.before, {p.relative_to(self.capture).as_posix(): p.read_bytes()
                                      for p in self.capture.rglob("*") if p.is_file()})
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(TEST_SEED, json.dumps(created) + self.output.read_text())

    def test_rfc8032_one_byte_reference_signature(self):
        key = self.root / "reference.pem"
        test_key(key, OTHER_SEED)
        (self.root / "message.bin").write_bytes(b"\x72")
        proc = subprocess.run([att._openssl(), "pkeyutl", "-sign", "-rawin", "-inkey",
                               str(key), "-in", str(self.root / "message.bin")],
                              capture_output=True, check=True)
        self.assertEqual(proc.stdout.hex(),
                         "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
                         "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00")

    def test_retained_signed_fixture_under_literal_external_selections(self):
        fixture = ROOT / "examples/capture-attestation/test-only.replay.attestation.json"
        checked = self.verify(attestation=fixture)
        self.assertEqual(checked["signature_integrity"], "CONFIRMED")
        self.assertEqual(checked["policy_authorization"], "NOT_ASSESSED")

    def test_repeated_signatures_are_immutable_replay_not_fresh_observations(self):
        first = self.sign()
        other = self.root / "again.json"
        second = self.sign(output=other)
        self.assertEqual(self.output.read_bytes(), other.read_bytes())
        self.assertEqual(first["attestation_digest"], second["attestation_digest"])
        self.assertEqual(self.verify()["freshness"], "UNKNOWN")

    def test_external_key_receipt_and_label_selections_fail_closed(self):
        self.sign()
        for overrides in ({"expected_key": "sha256:" + "0" * 64},
                          {"expected_receipt": "sha256:" + "0" * 64},
                          {"expected_signer": "other-reviewer"},
                          {"expected_key": TEST_PUBLIC},
                          {"expected_signer": "arbitrary/label"}):
            with self.subTest(overrides=overrides), self.assertRaises(review.ReviewError):
                self.verify(**overrides)

    def test_valid_unselected_key_signature_is_not_trusted(self):
        other_key = self.root / "other.pem"
        test_key(other_key, OTHER_SEED)
        other_pin = att.key_id(bytes.fromhex(OTHER_PUBLIC))
        self.sign(private_key=other_key, expected_key=other_pin)
        with self.assertRaises(review.ReviewError):
            self.verify()
        self.assertEqual(self.verify(expected_key=other_pin)["signature_integrity"], "CONFIRMED")

    def test_invalid_signature_rehash_and_statement_extensions_are_rejected(self):
        self.sign()
        original = json.loads(self.output.read_text())
        changes = []
        bad = copy.deepcopy(original)
        bad["signature"] = ("00" if bad["signature"][:2] != "00" else "01") + bad["signature"][2:]
        changes.append(bad)
        for field, value in (("role", "EXECUTION_WITNESS"), ("signer_id", "other-reviewer"),
                             ("scope", "INDEPENDENT_EXECUTION_PROOF"),
                             ("receipt_digest", "sha256:" + "0" * 64),
                             ("invocation_id", "00000000-0000-0000-0000-000000000001"),
                             ("source_build_binding", "CONFIRMED")):
            bad = copy.deepcopy(original)
            bad["statement"][field] = value
            changes.append(bad)
        bad = copy.deepcopy(original)
        bad["authority"] = "CONFIRMED"
        changes.append(bad)
        for index, bad in enumerate(changes):
            with self.subTest(control=index):
                self.mutate_attestation(bad)
                with self.assertRaises(review.ReviewError):
                    self.verify()

    def test_signed_receipt_transplant_to_another_valid_occurrence_is_rejected(self):
        self.sign()
        receipt = json.loads(self.before["receipt.json"])
        receipt["invocation_id"] = "00000000-0000-0000-0000-000000000001"
        new_pin = self.rehash_receipt(receipt)
        review.validate_capture(self.capture, new_pin)
        with self.assertRaises(review.ReviewError):
            self.verify(expected_receipt=new_pin)

    def test_modified_saved_bytes_and_freshly_rehashed_authority_are_rejected(self):
        self.sign()
        (self.capture / "provider.stdout").write_bytes(self.before["provider.stdout"] + b" ")
        with self.assertRaises(review.ReviewError):
            self.verify()
        (self.capture / "provider.stdout").write_bytes(self.before["provider.stdout"])
        receipt = json.loads(self.before["receipt.json"])
        receipt["authority"]["source_build_binding"] = "CONFIRMED"
        fresh_pin = self.rehash_receipt(receipt)
        with patch.object(att, "_crypto", side_effect=AssertionError("invalid bytes cannot be signed")):
            with self.assertRaises(review.ReviewError):
                self.sign(expected_receipt=fresh_pin, output=self.root / "forged.json")
        self.assertFalse((self.root / "forged.json").exists())

    def test_rejected_and_blocked_outcomes_can_be_signed_without_promotion(self):
        for outcome in ("REJECTED", "BLOCKED"):
            with self.subTest(outcome=outcome):
                receipt = json.loads(self.before["receipt.json"])
                for name, raw in self.before.items():
                    (self.capture / name).write_bytes(raw)
                if outcome == "REJECTED":
                    report = {"status": "REJECTED", "error": "test-only rejection fixture"}
                    raw = json.dumps(report).encode() + b"\n"
                    (self.capture / "provider.stdout").write_bytes(raw)
                    receipt["provider_report"] = report
                    receipt["invocation"].update(outcome=outcome, exit_code=2, reason=None,
                        stdout=review._artifact("provider.stdout", raw))
                else:
                    receipt["provider_report"] = None
                    receipt["invocation"].update(outcome=outcome, exit_code=None,
                                                 reason="test-only blocked fixture")
                pin = self.rehash_receipt(receipt)
                output = self.root / (outcome + ".json")
                self.sign(expected_receipt=pin, output=output)
                checked = self.verify(expected_receipt=pin, attestation=output)
                self.assertEqual(checked["capture_validation"]["provider_outcome"], outcome)
                self.assertEqual(checked["general_claim_verdict"], "NOT_ASSESSED")

    def test_duplicate_and_oversized_attestation_json_is_rejected(self):
        self.sign()
        original = self.output.read_bytes()
        for raw in (b'{"schema":"x","schema":"x"}', b" " * (att.MAX_ATTESTATION + 1),
                    original.replace(b'"algorithm":"Ed25519"', b'"algorithm":"Ed25519","algorithm":"Ed25519"'),
                    original.replace(b'"algorithm":"Ed25519"', b'"algorithm":NaN')):
            with self.subTest(size=len(raw)), self.assertRaises(review.ReviewError):
                self.output.write_bytes(raw)
                self.verify()

    def test_existing_inside_and_symlinked_capture_outputs_are_preserved(self):
        self.output.write_bytes(b"original output")
        symlink = self.root / "alias"
        symlink.symlink_to(self.capture, target_is_directory=True)
        for output in (self.output, self.capture / "attestation.json", symlink / "attestation.json"):
            with self.subTest(output=output), self.assertRaises(review.ReviewError):
                self.sign(output=output)
        self.assertEqual(self.output.read_bytes(), b"original output")
        self.assertFalse((self.capture / "attestation.json").exists())

    def test_shared_oversized_special_and_wrong_algorithm_keys_are_rejected(self):
        self.key.chmod(0o644)
        with self.assertRaises(review.ReviewError):
            self.sign()
        self.key.chmod(0o600)
        self.key.write_bytes(b"x" * (att.MAX_KEY + 1))
        with self.assertRaises(review.ReviewError):
            self.sign()
        fifo = self.root / "fifo-key"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(review.ReviewError):
            self.sign(private_key=fifo)
        ec_key = self.root / "wrong-algorithm.pem"
        subprocess.run([att._openssl(), "genpkey", "-algorithm", "EC", "-pkeyopt",
                        "ec_paramgen_curve:P-256", "-out", str(ec_key)], check=True, capture_output=True)
        ec_key.chmod(0o600)
        with self.assertRaises(review.ReviewError):
            self.sign(private_key=ec_key)
        self.assertFalse(self.output.exists())

    def test_missing_crypto_and_native_failure_never_create_an_attestation(self):
        with patch.object(att.shutil, "which", return_value=None), self.assertRaises(review.ReviewError):
            self.sign()
        with patch.object(att, "_bounded_process", return_value=(None, b"", b"secret diagnostic", "timeout")):
            with self.assertRaises(review.ReviewError) as caught:
                self.sign()
        self.assertNotIn("secret diagnostic", str(caught.exception))
        self.assertFalse(self.output.exists())

    def test_cli_separate_process_roundtrip_and_secret_diagnostics(self):
        command = [sys.executable, "-m", "chimera_one"]
        selected = ["--expect-receipt", CAPTURE_PIN, "--expect-key", KEY_PIN]
        proc = subprocess.run([*command, "attest-capture", str(self.capture), *selected,
                               "--key", str(self.key), "--signer-id", SIGNER,
                               "--output", str(self.output)], cwd=ROOT, capture_output=True, check=True)
        self.assertEqual(json.loads(proc.stdout)["status"], "SIGNED_NOT_AUTHORIZED")
        proc = subprocess.run([*command, "verify-capture-attestation", str(self.capture), *selected,
                               "--attestation", str(self.output), "--expect-signer", SIGNER],
                              cwd=ROOT, capture_output=True, check=True)
        self.assertEqual(json.loads(proc.stdout)["signature_integrity"], "CONFIRMED")
        self.key.write_bytes(b"TEST_SECRET_DIAGNOSTIC_DO_NOT_ECHO")
        proc = subprocess.run([*command, "attest-capture", str(self.capture), *selected,
                               "--key", str(self.key), "--signer-id", SIGNER,
                               "--output", str(self.root / "failed.json")], cwd=ROOT, capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["status"], "REJECTED")
        self.assertNotIn(b"TEST_SECRET_DIAGNOSTIC_DO_NOT_ECHO", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
