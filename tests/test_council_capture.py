"""Adapter boundaries using saved native bytes and explicit process doubles.

No test here claims fresh inference. The separate owned-model CI runs the actual
adapter, model weights and pinned external saved-transcript checker.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from chimera_one import council_capture as c
from chimera_one import cli
from chimera_one.offline_review import ReviewError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/council-budget/role-v2"


class CouncilCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="one-council-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / "provider"
        self.checkout.mkdir()
        self.suite = FIXTURE / "suite.json"
        self.report = json.loads((FIXTURE / "benchmark.json").read_bytes())
        self.output = self.root / "capture"
        selection = self.report["selection"]
        self.args = dict(checkout=self.checkout, suite=self.suite, output=self.output,
                         expected_suite=selection["suite_digest"], model=selection["model"],
                         expected_model=selection["model_manifest_digest"], repeats=2,
                         host="http://127.0.0.1:11434")
        self.snapshot = patch.object(c, "snapshot_provider", return_value=c.provider_ref())
        self.snapshot.start()
        self.addCleanup(self.snapshot.stop)

    def checked(self, report=None):
        report = self.report if report is None else report
        return {"schema": "chimera-budget-benchmark-validation/v2", "status": "CONFIRMED",
                "scope": c.REPORT_SCOPE, "report_digest": report["report_digest"],
                "suite_digest": report["selection"]["suite_digest"],
                "model_manifest_digest": report["selection"]["model_manifest_digest"],
                "summary": report["summary"], "raw_inference_reproduced": "NOT_RUN",
                "authority": c.REPORT_AUTHORITY}

    def native_double(self, command, cwd, **kwargs):
        if "measure" in command:
            Path(command[command.index("--output") + 1]).write_text(json.dumps(self.report))
            outcome = self.report["summary"]["status"]
            cli_report = {"schema": "chimera-budget-benchmark-cli/v2", "status": outcome,
                          "report_digest": self.report["report_digest"], "summary": self.report["summary"]}
            return (0 if outcome == "COMPLETED" else 3), json.dumps(cli_report).encode(), b"", None
        self.assertIn("validate", command)
        self.assertNotIn("--execute", command)
        self.assertNotIn("--host", command)
        return 0, json.dumps(self.checked()).encode(), b"", None

    def measure(self, **overrides):
        with patch.object(c, "_invoke", side_effect=self.native_double) as invoked:
            receipt = c.measure_council(**dict(self.args, **overrides))
        self.last_invocations = invoked.call_args_list
        return receipt

    def validate(self, receipt, **overrides):
        args = dict(root=self.output, checkout=self.checkout, expected_receipt=receipt["receipt_digest"],
                    expected_report=receipt["report_digest"], expected_suite=self.args["expected_suite"],
                    expected_model=self.args["expected_model"])
        args.update(overrides)
        with patch.object(c, "_invoke", side_effect=self.native_double):
            return c.validate_council_capture(**args)

    def reseal(self, receipt):
        for name in c.FILE_LIMITS:
            raw = (self.output / name).read_bytes()
            receipt["artifacts"][name] = {"sha256": c.sha256(raw), "size_bytes": len(raw)}
        receipt["receipt_digest"] = c.receipt_digest(receipt)
        (self.output / "receipt.json").write_text(json.dumps(receipt))
        return receipt

    def test_fixed_commands_private_capture_and_saved_recheck(self):
        receipt = self.measure()
        call = self.last_invocations[0]
        command = call.args[0]
        self.assertEqual(command[:3], [sys.executable, "-I", "-B"])
        self.assertEqual(command[4], c.BOOTSTRAP)
        self.assertIn("--execute", command)
        self.assertEqual(call.kwargs, {"timeout_seconds": 900})
        self.assertEqual(len(self.last_invocations), 2)
        self.assertEqual(receipt["invocation"]["outcome"], "COMPLETED")
        before = {p.relative_to(self.output).as_posix(): p.read_bytes()
                  for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual((self.output / "receipt.json").stat().st_mode & 0o777, 0o600)
        result = self.validate(receipt)
        self.assertEqual(result["fresh_inference"], "NOT_RUN")
        self.assertEqual(result["saved_transcripts_recomputed"], "CONFIRMED")
        self.assertEqual(result["summary"]["council_delivered_exact_matches"], 1)
        self.assertEqual(before, {p.relative_to(self.output).as_posix(): p.read_bytes()
                                 for p in self.output.rglob("*") if p.is_file()})
        self.assertFalse(Path(command[5]).exists())

    def test_all_external_pins_fail_closed(self):
        receipt = self.measure()
        for name in ("expected_receipt", "expected_report", "expected_suite", "expected_model"):
            with self.subTest(pin=name), self.assertRaises(ReviewError):
                self.validate(receipt, **{name: "sha256:" + "0" * 64})

    def test_resealed_authority_source_selection_and_boolean_exits_are_rejected(self):
        original = self.measure()
        mutations = [lambda r: r["authority"].update(general_intelligence="CONFIRMED"),
                     lambda r: r["provider"].update(revision="0" * 40),
                     lambda r: r["selection"].update(repeats=True),
                     lambda r: r["selection"].update(host="http://example.com:11434"),
                     lambda r: r["invocation"].update(exit_code=False),
                     lambda r: r["invocation"].update(checker_exit_code=False)]
        for mutation in mutations:
            receipt = copy.deepcopy(original)
            mutation(receipt)
            with self.subTest(mutation=mutation), self.assertRaises(ReviewError):
                self.validate(self.reseal(receipt))

    def test_substituted_provider_and_checker_transcripts_are_rejected_after_resealing(self):
        original = self.measure()
        for name in ("provider.stdout", "checker.stdout", "provider.stderr", "checker.stderr"):
            path = self.output / name
            saved = path.read_bytes()
            path.write_bytes(saved + b"substituted")
            with self.subTest(file=name), self.assertRaises((ReviewError, ValueError)):
                self.validate(self.reseal(copy.deepcopy(original)))
            path.write_bytes(saved)

    def test_capture_inventory_symlinks_and_bounds(self):
        receipt = self.measure()
        extra = self.output / "unexpected"
        extra.write_text("not selected")
        with self.assertRaises(ReviewError):
            self.validate(receipt)
        extra.unlink()
        extra.symlink_to(self.output / "benchmark.json")
        with self.assertRaises(ReviewError):
            self.validate(receipt)
        extra.unlink()
        (self.output / "provider.stdout").write_bytes(b"x" * 131073)
        with self.assertRaises(ReviewError):
            self.validate(self.reseal(receipt))

    def test_blocked_capture_preserves_failure_and_requires_explicit_not_run(self):
        with patch.object(c, "_invoke", return_value=(None, b"bounded native failure", b"diagnostic", "provider timeout")):
            receipt = c.measure_council(**self.args)
        self.assertEqual(receipt["invocation"]["outcome"], "BLOCKED")
        self.assertEqual((self.output / "provider.stdout").read_bytes(), b"bounded native failure")
        with self.assertRaises(ReviewError):
            self.validate(receipt)
        with patch.object(c, "snapshot_provider", side_effect=AssertionError("blocked capture probed source")), \
                patch.object(c, "_invoke", side_effect=AssertionError("blocked capture spawned process")):
            result = c.validate_council_capture(root=self.output, checkout=self.checkout,
                        expected_receipt=receipt["receipt_digest"], expected_report="NOT_RUN",
                        expected_suite=self.args["expected_suite"], expected_model=self.args["expected_model"])
        self.assertEqual(result["scope"], "CAPTURE_BYTES_ONLY")
        self.assertEqual(result["saved_transcripts_recomputed"], "NOT_RUN")

    def test_incomplete_does_not_become_completed(self):
        # Deliberately synthetic process-double report; the real external checker
        # separately enforces native trace completeness and reference scores.
        self.report["summary"]["status"] = "INCOMPLETE"
        self.report["report_digest"] = c.ag_digest("budget-benchmark/v2", {k: v for k, v in self.report.items() if k != "report_digest"})
        receipt = self.measure()
        self.assertEqual(receipt["invocation"]["outcome"], "INCOMPLETE")
        self.assertEqual(self.validate(receipt)["captured_outcome"], "INCOMPLETE")
        receipt["invocation"].update(outcome="COMPLETED", exit_code=0)
        with self.assertRaises(ReviewError):
            self.validate(self.reseal(receipt))

    def test_failed_checker_cannot_leave_a_successful_capture(self):
        def invoke(command, cwd, **kwargs):
            if "measure" in command:
                return self.native_double(command, cwd, **kwargs)
            return 2, b"rejected", b"", None
        with patch.object(c, "_invoke", side_effect=invoke):
            receipt = c.measure_council(**self.args)
        self.assertEqual(receipt["invocation"]["outcome"], "BLOCKED")
        self.assertIsNone(receipt["report_digest"])
        self.assertEqual((self.output / "checker.stdout").read_bytes(), b"rejected")

    def test_unsupported_hosts_models_repeats_and_existing_output_never_invoke(self):
        for overrides in ({"host": "https://127.0.0.1:11434"}, {"host": "http://127.0.0.1:11434/?x=1"},
                          {"host": "http://user@127.0.0.1:11434"}, {"host": "http://localhost:11434"},
                          {"host": "http://127.0.0.1:80"}, {"model": "qwen-cloud"},
                          {"model": "--external"}, {"repeats": True}, {"repeats": 4}):
            with self.subTest(overrides=overrides), patch.object(c, "_invoke", side_effect=AssertionError("inference started")), self.assertRaises(ReviewError):
                c.measure_council(**dict(self.args, **overrides))
        self.output.mkdir()
        with patch.object(c, "_invoke", side_effect=AssertionError("inference started")), self.assertRaises(ReviewError):
            c.measure_council(**self.args)

    def test_dry_run_probes_nothing(self):
        args = cli.build_parser().parse_args(["measure-chimera-council", "--chimera-checkout", "missing",
            "--suite", "missing", "--model", "qwen2.5:1.5b", "--expect-suite", "unselected",
            "--expect-model", "unselected", "--output", "missing"])
        with patch.object(cli, "measure_council", side_effect=AssertionError("dry run executed")), patch("builtins.print") as output:
            self.assertEqual(args.func(args), 0)
        self.assertEqual(json.loads(output.call_args.args[0])["inference_calls"], 0)


class ProviderSnapshotTests(unittest.TestCase):
    def test_exact_source_identity_cleanliness_and_bytes_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary) / "source"
            checkout.mkdir()
            target = Path(temporary) / "private"
            git_values = {("remote", "get-url", "origin"): "https://github.com/" + c.REPOSITORY + ".git",
                          ("rev-parse", "HEAD"): c.REVISION, ("rev-parse", "HEAD^{tree}"): c.TREE,
                          ("status", "--porcelain"): ""}
            def git(path, *argv):
                return git_values[argv]
            # This is a source-boundary double, never executable provider evidence.
            manifest = json.dumps({"repository": c.REPOSITORY, "control_plane": "aixaria0/CHIMERA-ONE", "version": "0.13.0"}).encode()
            source = b"UNIT SOURCE DOUBLE, never executed"
            for name in ("chimera.provider.json", *c.SOURCE_FILES):
                p = checkout / name
                p.parent.mkdir(exist_ok=True)
                p.write_bytes(manifest if name == "chimera.provider.json" else source)
            with patch.object(c, "_git", side_effect=git), patch.object(c, "MANIFEST_SHA256", c.sha256(manifest)), \
                    patch.object(c, "SOURCE_FILES", {name: c.sha256(source) for name in c.SOURCE_FILES}):
                self.assertEqual(c.snapshot_provider(checkout, target)["revision"], c.REVISION)
                self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}, set(c.SOURCE_FILES))
                for key, bad in ((('rev-parse', 'HEAD'), "0" * 40), (('rev-parse', 'HEAD^{tree}'), "0" * 40),
                                 (('remote', 'get-url', 'origin'), "https://github.com/other/Chimera-AG"),
                                 (('status', '--porcelain'), " M chimera/council.py")):
                    original = git_values[key]
                    git_values[key] = bad
                    with self.subTest(field=key), self.assertRaises(ReviewError):
                        c.snapshot_provider(checkout, target)
                    git_values[key] = original
                (checkout / "chimera/council.py").write_bytes(b"changed")
                with self.assertRaises(ReviewError):
                    c.snapshot_provider(checkout, target)


if __name__ == "__main__":
    unittest.main()
