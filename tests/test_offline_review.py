"""Local provider doubles test the boundary; real OMEGA has separate conformance."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chimera_one import offline_review as review
from chimera_one.catalog import load_catalog

ROOT = Path(__file__).resolve().parents[1]


def provider_identity():
    return {"repository": review.OMEGA_REPOSITORY, "revision": review.OMEGA_REVISION,
            "tree": review.OMEGA_TREE, "manifest_sha256": review.OMEGA_MANIFEST_SHA256}


def native_report(context):
    report = {"schema": review.REPORT_SCHEMA, "scope": review.REPORT_SCOPE, "status": "CONFIRMED",
              "context_digest": review.omega_digest("aether/historical-context/v1", context),
              "source_repository": "aixaria0/aether-runtime",
              "lineage_source_revision": "04d785f7beee5ff96d78e092a1d73b79987c9e0e",
              "journal_export_source_revision": "30dad8ec794e3f27600bfc0a5a5df072e79ba8c4",
              "runtime_reproduction": "NOT_RUN", "omega_core_verdict": "NOT_RUN",
              "direct_replay_binding": "NOT_APPLICABLE", "parent_receipt_event_binding": "NOT_APPLICABLE",
              "producer_view": {"authority": "ATTRIBUTED_ONLY", "assessment": "rejected"}}
    for field in ("registry_digest", "journal_export_digest", "certificate_digest",
                  "journal_head_sha256", "journal_event_count"):
        report[field] = context[field]
    for field in ("registry_freshness", "historical_time_authorization", "current_live_key_authorization",
                  "external_journal_anchor", "independent_observation", "producer_binary_attestation"):
        report[field] = "UNKNOWN"
    for field in ("signature_integrity", "raw_operation_binding", "selected_policy_binding",
                  "registry_authorization_binding", "journal_chain_integrity",
                  "journal_sequence_integrity", "receipt_event_binding"):
        report[field] = "CONFIRMED"
    return report


class OfflineReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="one-owned-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / "provider"
        self.checkout.mkdir()
        self.export = {"lineage": {"certificate": {"test_only": "synthetic provider-double input"}}}
        self.registry = {"test_only": "synthetic reviewed registry"}
        self.context = {"schema": "chimera-aether-historical-context/v1",
                        "source_repository": "aixaria0/aether-runtime",
                        "source_revision": "30dad8ec794e3f27600bfc0a5a5df072e79ba8c4",
                        "registry_digest": review.omega_digest("aether/historical-registry/v1", self.registry),
                        "journal_export_digest": review.omega_digest("aether/journal-export/v1", self.export),
                        "certificate_digest": review.omega_digest("aether/lattice-certificate/v1", self.export["lineage"]["certificate"]),
                        "journal_head_sha256": "a" * 64, "journal_event_count": 1}
        self.paths = {}
        for name in ("export", "registry", "context"):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(getattr(self, name), indent=2) + "\n")
            self.paths[name] = path
        self.before = {name: p.read_bytes() for name, p in self.paths.items()}
        self.binary = self.root / "provider-double"
        self.report = native_report(self.context)
        self.make_binary()
        self.inspection = patch.object(review, "inspect_provider", return_value=provider_identity())
        self.inspection.start()
        self.addCleanup(self.inspection.stop)

    def make_binary(self, prefix="", report=None, exit_code=0):
        body = (f"#!{sys.executable}\nimport json, os, pathlib, sys, time\n"
                + prefix + "\n"
                + "sys.stderr.write('test-only provider diagnostic\\n')\n"
                + f"print({json.dumps(self.report if report is None else report)!r})\n"
                + f"raise SystemExit({exit_code})\n")
        self.binary.write_text(body)
        self.binary.chmod(0o700)

    def invoke(self, output="capture", **overrides):
        arguments = {"checkout": self.checkout, "binary": self.binary,
                     "expected_binary": review.sha256(self.binary.read_bytes()),
                     "expected_context": review.omega_digest("aether/historical-context/v1", self.context),
                     "output": self.root / output, **self.paths}
        arguments.update(overrides)
        return review.review_aether_history(**arguments)

    def test_capture_retains_exact_bytes_native_report_and_unknown_authority(self):
        receipt = self.invoke()
        self.assertEqual(receipt["provider_report"], self.report)
        self.assertEqual(receipt["invocation"]["outcome"], "CONFIRMED")
        self.assertEqual(receipt["provider_report"]["producer_view"]["assessment"], "rejected")
        self.assertEqual(receipt["authority"]["source_build_binding"], "UNKNOWN")
        self.assertEqual(receipt["authority"]["general_claim_verdict"], "NOT_ASSESSED")
        self.assertEqual(receipt["authority"]["os_network_sandbox"], "NOT_ESTABLISHED")
        for name, raw in self.before.items():
            self.assertEqual(self.paths[name].read_bytes(), raw)
            self.assertEqual((self.root / "capture/inputs" / f"{name}.json").read_bytes(), raw)
        checked = review.validate_capture(self.root / "capture", receipt["receipt_digest"])
        self.assertEqual(checked["provider_execution_reproduced"], "NOT_RUN")

    def test_repeated_invocations_have_distinct_occurrences(self):
        a, b = self.invoke("a"), self.invoke("b")
        self.assertNotEqual(a["invocation_id"], b["invocation_id"])
        self.assertNotEqual(a["receipt_digest"], b["receipt_digest"])
        self.assertEqual(a["provider_report"], b["provider_report"])

    def test_provider_rejection_is_retained_without_turning_into_verifier_success(self):
        rejected = {"status": "REJECTED", "error": "test-only rejected receipt"}
        self.make_binary(report=rejected, exit_code=2)
        receipt = self.invoke()
        self.assertEqual(receipt["invocation"]["outcome"], "REJECTED")
        self.assertEqual(receipt["provider_report"], rejected)
        self.assertEqual(review.validate_capture(self.root / "capture", receipt["receipt_digest"])["provider_outcome"], "REJECTED")

    def test_binary_and_external_context_pins_fail_before_provider_invocation(self):
        marker = self.root / "provider-was-started"
        self.make_binary(prefix=f"pathlib.Path({str(marker)!r}).write_text('started')")
        for arguments in ({"expected_binary": "0" * 64}, {"expected_context": "0" * 64},
                          {"expected_binary": "bad"}):
            with self.assertRaises(review.ReviewError):
                self.invoke(**arguments)
            self.assertFalse(marker.exists())
            self.assertFalse((self.root / "capture").exists())

    def test_existing_outputs_and_provider_checkout_are_preserved(self):
        out = self.root / "capture"
        out.mkdir()
        (out / "keep.txt").write_text("do not replace")
        with self.assertRaises(review.ReviewError):
            self.invoke()
        self.assertEqual((out / "keep.txt").read_text(), "do not replace")
        with self.assertRaises(review.ReviewError):
            self.invoke(output="provider/result")
        link = self.root / "provider-link"
        link.symlink_to(self.checkout, target_is_directory=True)
        with self.assertRaises(review.ReviewError):
            self.invoke(output="provider-link/result")

    def test_timeout_and_output_overflow_leave_bounded_blocked_captures(self):
        for name, prefix in (("timeout", "time.sleep(5)"),
                             ("overflow", f"os.write(1, b'x' * {review.MAX_OUTPUT + 16384}); time.sleep(5)")):
            self.make_binary(prefix=prefix)
            with patch.object(review, "TIMEOUT_SECONDS", 0.3):
                receipt = self.invoke(name)
            self.assertEqual(receipt["invocation"]["outcome"], "BLOCKED")
            self.assertLessEqual(receipt["invocation"]["stdout"]["size_bytes"], review.MAX_OUTPUT)
            self.assertEqual(review.validate_capture(self.root / name, receipt["receipt_digest"])["provider_outcome"], "BLOCKED")

    def test_signal_exit_is_blocked_and_can_be_archived(self):
        self.make_binary(prefix="os.kill(os.getpid(), 15)")
        receipt = self.invoke()
        self.assertEqual(receipt["invocation"]["outcome"], "BLOCKED")
        self.assertIsNone(receipt["invocation"]["exit_code"])
        review.validate_capture(self.root / "capture", receipt["receipt_digest"])

    def test_provider_snapshot_mutation_is_blocked_originals_remain_intact(self):
        self.make_binary(prefix="pathlib.Path(sys.argv[2]).write_text('{}')")
        receipt = self.invoke()
        self.assertEqual(receipt["invocation"]["outcome"], "BLOCKED")
        self.assertFalse(receipt["invocation"]["input_snapshots_unchanged"])
        self.assertEqual(self.paths["export"].read_bytes(), self.before["export"])
        self.assertEqual((self.root / "capture/inputs/export.json").read_bytes(), self.before["export"])
        review.validate_capture(self.root / "capture", receipt["receipt_digest"])

    def test_provider_cannot_promote_dimensions_or_change_selected_context(self):
        for index, (field, value) in enumerate((("omega_core_verdict", "CONFIRMED"),
                                               ("registry_freshness", "CONFIRMED"),
                                               ("context_digest", "f" * 64),
                                               ("scope", "GLOBAL_TRUTH"),
                                               ("signature_integrity", "UNKNOWN"))):
            changed = copy.deepcopy(self.report)
            changed[field] = value
            self.make_binary(report=changed)
            receipt = self.invoke(f"changed-{index}")
            self.assertEqual(receipt["invocation"]["outcome"], "BLOCKED")
            self.assertIsNone(receipt["provider_report"])
        self.make_binary(exit_code=2)
        self.assertEqual(self.invoke("wrong-exit")["invocation"]["outcome"], "BLOCKED")

    def test_capture_substitution_rehashing_and_authority_promotion_fail_closed(self):
        receipt = self.invoke()
        root = self.root / "capture"
        with self.assertRaises(review.ReviewError):
            review.validate_capture(root, "sha256:" + "0" * 64)
        (root / "provider.stderr").write_bytes(b"changed diagnostic")
        with self.assertRaises(review.ReviewError):
            review.validate_capture(root, receipt["receipt_digest"])
        (root / "provider.stderr").write_bytes(b"test-only provider diagnostic\n")
        changed = copy.deepcopy(receipt)
        changed["authority"]["source_build_binding"] = "CONFIRMED"
        changed["receipt_digest"] = review.receipt_digest(changed)
        review._write_receipt(root, changed)
        for pin in (receipt["receipt_digest"], changed["receipt_digest"]):
            with self.assertRaises(review.ReviewError):
                review.validate_capture(root, pin)

    def test_capture_input_swapping_is_rejected_even_after_fresh_receipt_selection(self):
        receipt = self.invoke()
        root = self.root / "capture"
        raw = b'{"swapped":true}'
        (root / "inputs/export.json").write_bytes(raw)
        receipt["inputs"]["export"] = review._artifact("inputs/export.json", raw)
        receipt["receipt_digest"] = review.receipt_digest(receipt)
        review._write_receipt(root, receipt)
        with self.assertRaises(review.ReviewError):
            review.validate_capture(root, receipt["receipt_digest"])

    def test_bounded_json_rejects_ambiguity_numbers_depth_strings_and_special_files(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":1.5}', b'{"x":-1}', b'{"x":NaN}',
                    b'{"x":9007199254740992}', b'[' * 33 + b'0' + b']' * 33,
                    json.dumps({"x": "a" * 4097}).encode(), b'{"x":"\\ud800"}'):
            with self.assertRaises(review.ReviewError):
                review._json(raw)
        huge = self.root / "huge.json"
        huge.write_bytes(b' ' * (review.MAX_INPUT + 1))
        with self.assertRaises(review.ReviewError):
            self.invoke(export=huge)
        fifo = self.root / "not-a-regular-file"
        os.mkfifo(fifo)
        with self.assertRaises(review.ReviewError):
            review._bounded_read(fifo)

    def test_source_revision_tree_owner_cleanliness_and_manifest_are_independent_gates(self):
        self.inspection.stop()
        manifest = {"repository": review.OMEGA_REPOSITORY, "control_plane": "aixaria0/CHIMERA-ONE",
                    "entrypoints": [{"capability": review.CAPABILITY, "mode": "verification", "network": "none", "mutation": "none"}]}
        raw = json.dumps(manifest).encode()
        (self.checkout / "chimera.provider.json").write_bytes(raw)
        valid = [review.OMEGA_REVISION, review.OMEGA_TREE, "git@github.com:aixaria0/CHIMERA-OMEGA.git", ""]
        with patch.object(review, "OMEGA_MANIFEST_SHA256", review.sha256(raw)):
            with patch.object(review, "_git", side_effect=valid):
                self.assertEqual(review.inspect_provider(self.checkout)["revision"], review.OMEGA_REVISION)
            for index, value in ((0, "0" * 40), (1, "f" * 40),
                                 (2, "https://github.com/someone/CHIMERA-OMEGA"), (3, " M file")):
                changed = list(valid)
                changed[index] = value
                with patch.object(review, "_git", side_effect=changed), self.assertRaises(review.ReviewError):
                    review.inspect_provider(self.checkout)
            manifest["entrypoints"][0]["network"] = "explicit"
            altered = json.dumps(manifest).encode()
            (self.checkout / "chimera.provider.json").write_bytes(altered)
            with patch.object(review, "OMEGA_MANIFEST_SHA256", review.sha256(altered)):
                with patch.object(review, "_git", side_effect=valid), self.assertRaises(review.ReviewError):
                    review.inspect_provider(self.checkout)

    def test_cli_usage_and_unselected_capture_have_structured_failures(self):
        result = subprocess.run([sys.executable, "-m", "chimera_one", "validate-capture",
                                 str(self.root), "--expect-receipt", "sha256:" + "0" * 64],
                                cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "REJECTED")

    def test_current_omega_capabilities_are_registered_without_network_or_mutation(self):
        capabilities = {c.id: c for c in load_catalog(ROOT / "capabilities/catalog.json")}
        for name in ("omega.verify-aether-lineage", "omega.verify-aether-journal",
                     "omega.verify-audit-archive", review.CAPABILITY):
            self.assertEqual(capabilities[name].provider, "CHIMERA-OMEGA")
            self.assertEqual(capabilities[name].raw["trust"]["network"], "none")
            self.assertEqual(capabilities[name].raw["trust"]["mutation"], "none")

    def test_retained_real_capture_validates_without_reinvoking_provider(self):
        root = ROOT / "examples/offline-review/replay"
        selected = "sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2"
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        with patch.object(review, "_invoke", side_effect=AssertionError("provider must not be invoked")):
            checked = review.validate_capture(root, selected)
        self.assertEqual(checked["provider_outcome"], "CONFIRMED")
        self.assertEqual(checked["provider_execution_reproduced"], "NOT_RUN")
        self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()})
        result = subprocess.run([sys.executable, "-m", "chimera_one", "validate-capture", str(root),
                                 "--expect-receipt", selected], cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["receipt_digest"], selected)


if __name__ == "__main__":
    unittest.main()
