"""Build-bridge boundaries; native acquisition has separate retained evidence.

Process doubles exercise the adapter without pretending that dummy archives or
version labels establish a real source build. The real native fixture is separate.
"""
from __future__ import annotations

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

from chimera_one import capture_build as build
from chimera_one import offline_review as review

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PIN = "sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2"
NATIVE_BINARY = "3989b0b32395b21f1d33468e3af65225e36c22ea28fa7e931807bb8b02a54d10"


class CaptureBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="one-build-bridge-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.capture = self.root / "capture"
        shutil.copytree(ROOT / "examples/offline-review/replay", self.capture)
        receipt = json.loads((self.capture / "receipt.json").read_text())
        self.pins = dict(expected_receipt=CAPTURE_PIN, expected_binary=receipt["binary_sha256"],
                         expected_controller=build.CHECKER_SHA256, expected_left="sha256:" + "1" * 64,
                         expected_right="sha256:" + "2" * 64, left_builder="unit-a", right_builder="unit-b")
        self.selection = build.select(**self.pins)
        self.checkout = self.root / "test-only-checker"
        self.checkout.mkdir()
        self.left, self.right = self.root / "left", self.root / "right"
        for folder in (self.left, self.right):
            folder.mkdir()
            for name in build.BUILD_FILES:
                path = folder / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b"TEST DOUBLE: not native build evidence")
        self.link = self.root / "link.json"
        self.before = {p.relative_to(self.capture).as_posix(): p.read_bytes()
                       for p in self.capture.rglob("*") if p.is_file()}
        self.script = ("import sys\nprint(" + repr(json.dumps(build._comparison(self.selection), indent=2, sort_keys=True)) + ")\n").encode()
        self.inspect = patch.object(build, "inspect_checker", return_value=self.script)
        self.checker_double = self.inspect.start()
        self.addCleanup(self.inspect.stop)

    def bind(self, **overrides):
        args = dict(root=self.capture, checker_checkout=self.checkout, left=self.left, right=self.right,
                    output=self.link, **self.pins)
        args.update(overrides)
        return build.bind_capture_build(**args)

    def validate(self, **overrides):
        args = dict(root=self.capture, link=self.link, expected_link=self.created["link_digest"], **self.pins)
        args.update(overrides)
        return build.validate_capture_build(**args)

    def reverify(self, **overrides):
        args = dict(root=self.capture, link=self.link, expected_link=self.created["link_digest"],
                    checker_checkout=self.checkout, left=self.left, right=self.right, **self.pins)
        args.update(overrides)
        return build.reverify_capture_build(**args)

    def rewrite(self, value):
        value["link_digest"] = build.link_digest(value)
        self.link.write_text(json.dumps(value))
        return value["link_digest"]

    def test_owned_checker_process_and_saved_mode_have_distinct_scopes(self):
        with patch.object(build, "_invoke", wraps=build._invoke) as invoked:
            self.created = self.bind()
            command = invoked.call_args.args[0]
            self.assertEqual(command[:3], [sys.executable, "-I", "-B"])
            self.assertEqual(command[4], "compare")
        with patch.object(build, "_invoke", side_effect=AssertionError("saved mode spawned checker")), \
                patch.object(build, "_git", side_effect=AssertionError("saved mode inspected Git")), \
                patch.object(review, "review_aether_history", side_effect=AssertionError("provider rerun")):
            report = self.validate()
        self.assertEqual(report["mode"], "SAVED_CAPTURE_AND_ATTRIBUTED_BUILD_REPORT_ONLY")
        self.assertEqual(report["raw_build_evidence_reverified"], "NOT_RUN")
        full = self.reverify()
        self.assertEqual(full["mode"], "REVERIFIED_EXTERNAL_SAVED_SOURCE_AND_BINARY_BYTES")
        self.assertEqual(full["raw_build_evidence_reverified"], "CONFIRMED")
        self.assertEqual(self.before, {p.relative_to(self.capture).as_posix(): p.read_bytes()
                                      for p in self.capture.rglob("*") if p.is_file()})
        self.assertEqual(self.link.stat().st_mode & 0o777, 0o600)
        for field in ("independent_observation", "organizational_independence", "hardware_independence",
                      "compiler_correctness", "toolchain_closure", "freshness"):
            self.assertEqual(full[field], "UNKNOWN")
        for field in ("provider_execution_reproduced", "build_reexecution", "target_runtime_reproduction"):
            self.assertEqual(full[field], "NOT_RUN")

    def test_all_external_selections_fail_closed(self):
        self.created = self.bind()
        for name, wrong in {"expected_receipt": "sha256:" + "0" * 64, "expected_link": "sha256:" + "0" * 64,
                            "expected_binary": "0" * 64, "expected_controller": "0" * 64,
                            "expected_left": "sha256:" + "3" * 64, "expected_right": "sha256:" + "4" * 64,
                            "left_builder": "wrong-a", "right_builder": "wrong-b"}.items():
            with self.subTest(pin=name), self.assertRaises(review.ReviewError):
                self.validate(**{name: wrong})

    def test_native_build_selection_cannot_relabel_historical_arm64_capture(self):
        marker = self.root / "checker-started"
        script = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n".encode() + self.script
        self.checker_double.return_value = script
        with self.assertRaisesRegex(review.ReviewError, "selected binary"):
            self.bind(expected_binary=NATIVE_BINARY)
        self.assertFalse(marker.exists())
        self.assertFalse(self.link.exists())

    def test_rehashed_transplant_onto_a_new_capture_occurrence_is_rejected(self):
        self.created = self.bind()
        receipt = json.loads((self.capture / "receipt.json").read_text())
        receipt["invocation_id"] = "81c62c45-6c5e-4f32-9912-79df965a57a4"
        receipt["receipt_digest"] = review.receipt_digest(receipt)
        (self.capture / "receipt.json").write_text(json.dumps(receipt))
        review.validate_capture(self.capture, receipt["receipt_digest"])
        value = json.loads(self.link.read_text())
        value["capture"]["receipt_digest"] = receipt["receipt_digest"]
        selected_link = self.rewrite(value)
        with self.assertRaisesRegex(review.ReviewError, "selected capture"):
            self.validate(expected_receipt=receipt["receipt_digest"], expected_link=selected_link)

    def test_authority_promotion_rejected_even_with_fresh_link_pin(self):
        self.created = self.bind()
        original = json.loads(self.link.read_text())
        for path, field in (("authority", "organizational_independence"), ("authority", "compiler_correctness"),
                            ("authority", "general_claim_verdict"), ("authority", "signer_authorization")):
            value = copy.deepcopy(original)
            value[path][field] = "CONFIRMED"
            with self.subTest(field=field), self.assertRaises(review.ReviewError):
                self.validate(expected_link=self.rewrite(value))
        value = copy.deepcopy(original)
        value["authorized"] = True
        with self.assertRaises(review.ReviewError):
            self.validate(expected_link=self.rewrite(value))

    def test_changed_checker_report_and_boolean_exit_do_not_pass_saved_validation(self):
        self.created = self.bind()
        original = json.loads(self.link.read_text())
        for mutate in (lambda v: v["checker_invocation"].update(exit_code=False),
                       lambda v: v["checker_invocation"].update(stdout_utf8="{}"),
                       lambda v: v["checker_invocation"].update(stderr_utf8="invented diagnostic"),
                       lambda v: v["comparison"]["dimensions"].update(general_claim="CONFIRMED")):
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(review.ReviewError):
                self.validate(expected_link=self.rewrite(value))

    def test_saved_mode_cannot_claim_raw_reverification_after_transcript_rehash(self):
        self.created = self.bind()
        value = json.loads(self.link.read_text())
        value["checker_invocation"]["stdout_utf8"] += "\n"
        selected = self.rewrite(value)
        self.assertEqual(self.validate(expected_link=selected)["raw_build_evidence_reverified"], "NOT_RUN")
        with self.assertRaisesRegex(review.ReviewError, "transcript"):
            self.reverify(expected_link=selected)

    def test_checker_failed_malformed_and_scope_promoted_outputs_leave_no_link(self):
        promoted = build._comparison(self.selection)
        promoted["dimensions"]["organizational_independence"] = "CONFIRMED"
        for script in (b"print('{}')", b"raise SystemExit(2)", b"print('not JSON')",
                       b"print(" + repr(json.dumps(promoted)).encode() + b")"):
            self.checker_double.return_value = script
            with self.assertRaises(review.ReviewError):
                self.bind()
            self.assertFalse(self.link.exists())

    def test_checker_timeout_and_output_overflow_are_bounded(self):
        for script in (b"import time; time.sleep(1)", b"print('x'*200000)"):
            self.checker_double.return_value = script
            with patch.object(review, "TIMEOUT_SECONDS", 0.1), self.assertRaises(review.ReviewError):
                self.bind()
            self.assertFalse(self.link.exists())

    def test_missing_extra_symlink_and_sparse_oversized_build_members_rejected(self):
        member = self.left / "build-1/omega"
        original = member.read_bytes()
        member.unlink()
        with self.assertRaises(review.ReviewError):
            self.bind()
        member.symlink_to(self.right / "build-1/omega")
        with self.assertRaises(review.ReviewError):
            self.bind()
        member.unlink()
        member.write_bytes(original)
        extra = self.left / "authority.json"
        extra.write_text("{}")
        with self.assertRaises(review.ReviewError):
            self.bind()
        extra.unlink()
        with member.open("wb") as stream:
            stream.truncate(build.BUILD_FILES["build-1/omega"] + 1)
        with self.assertRaises(review.ReviewError):
            self.bind()

    def test_existing_and_protected_outputs_preserved(self):
        self.link.write_text("preserve")
        for output in (self.link, self.capture / "link.json", self.left / "link.json", self.checkout / "link.json"):
            with self.assertRaises(review.ReviewError):
                self.bind(output=output)
        self.assertEqual(self.link.read_text(), "preserve")

    def test_checker_identity_does_not_accept_new_source_head_or_dirty_checkout(self):
        def git(_, *args):
            return {("remote", "get-url", "origin"): "https://github.com/" + review.OMEGA_REPOSITORY,
                    ("rev-parse", "HEAD"): review.OMEGA_REVISION,
                    ("rev-parse", "HEAD^{tree}"): build.CHECKER_TREE, ("status", "--porcelain"): ""}[args]
        self.inspect.stop()
        with patch.object(build, "_git", side_effect=git), self.assertRaises(review.ReviewError):
            build.inspect_checker(self.checkout)
        self.checker_double = self.inspect.start()

    def test_duplicate_json_and_size_limit_rejected(self):
        self.created = self.bind()
        value = self.link.read_text().strip()
        self.link.write_text(value[:-1] + ',"scope":"' + build.SCOPE + '"}')
        with self.assertRaises(review.ReviewError):
            self.validate()
        with self.link.open("wb") as stream:
            stream.truncate(build.MAX_LINK + 1)
        with self.assertRaises(review.ReviewError):
            self.validate()

    def test_linking_a_rejected_capture_does_not_promote_its_outcome(self):
        receipt = json.loads((self.capture / "receipt.json").read_text())
        raw = b'{"status":"REJECTED","error":"test-only rejected input"}\n'
        (self.capture / "provider.stdout").write_bytes(raw)
        receipt["provider_report"] = json.loads(raw)
        receipt["invocation"].update(exit_code=2, outcome="REJECTED", reason=None,
                                     stdout=review._artifact("provider.stdout", raw))
        receipt["receipt_digest"] = review.receipt_digest(receipt)
        self.pins["expected_receipt"] = receipt["receipt_digest"]
        (self.capture / "receipt.json").write_text(json.dumps(receipt))
        self.created = self.bind()
        self.assertEqual(self.created["provider_outcome"], "REJECTED")
        self.assertEqual(self.validate()["capture_validation"]["provider_outcome"], "REJECTED")
        self.assertEqual(receipt["authority"]["source_build_binding"], "UNKNOWN")

    def test_saved_cli_requires_pins_and_never_needs_external_checkout(self):
        self.created = self.bind()
        args = [sys.executable, "-B", "-m", "chimera_one", "validate-capture-build", str(self.capture),
                "--link", str(self.link), "--expect-link", self.created["link_digest"]]
        mapping = {"expected_receipt": "expect-receipt", "expected_binary": "expect-omega-binary",
                   "expected_controller": "expect-controller", "expected_left": "expect-left-record",
                   "expected_right": "expect-right-record", "left_builder": "left-builder", "right_builder": "right-builder"}
        for key, option in mapping.items():
            args += ["--" + option, self.pins[key]]
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["raw_build_evidence_reverified"], "NOT_RUN")
        args[args.index("--expect-omega-binary") + 1] = "0" * 64
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "REJECTED")


class RetainedNativeBuildLinkTests(unittest.TestCase):
    def test_real_native_capture_link_is_validated_without_external_execution(self):
        fixture = ROOT / "examples/capture-build/native-replay"
        with patch.object(build, "_invoke", side_effect=AssertionError("native binary/checker execution")), \
                patch.object(build, "_git", side_effect=AssertionError("private checkout access")):
            report = build.validate_capture_build(
                root=fixture / "capture", link=fixture / "build-link.json",
                expected_receipt="sha256:8832edd572eb04f9cab4f24c082628a66f429dc93ef0945e7cf7025f9ee1861d",
                expected_link="sha256:499bad56abc83a7da78928d6557a6429eacfdbc4e60cee634f33d58a8f103419",
                expected_binary=NATIVE_BINARY, expected_controller=build.CHECKER_SHA256,
                expected_left="sha256:02249909a7fbd5e5007785b6f4ceb5621b6ad89a34c0f3d4669784e6b9ccad26",
                expected_right="sha256:c050c79699b77eb86afc11c9642d164f4ec364c487dcc1841ab3e1ab6714649a",
                left_builder="builder-a", right_builder="builder-b")
        self.assertEqual(report["capture_validation"]["provider_outcome"], "CONFIRMED")
        self.assertEqual(report["raw_build_evidence_reverified"], "NOT_RUN")
        self.assertEqual(report["build_execution"], "ATTRIBUTED_NOT_ATTESTED")

    def test_previously_reverified_report_is_not_treated_as_a_current_raw_check(self):
        fixture = ROOT / "examples/capture-build/native-replay"
        old = json.loads((fixture / "reverify-capture-build.json").read_text())
        saved = json.loads((fixture / "validate-capture-build.json").read_text())
        self.assertEqual(old["raw_build_evidence_reverified"], "CONFIRMED")
        self.assertEqual(saved["raw_build_evidence_reverified"], "NOT_RUN")
        self.assertEqual(old["link_digest"], saved["link_digest"])
        self.assertEqual(old["receipt_digest"], saved["receipt_digest"])


if __name__ == "__main__":
    unittest.main()
