#!/usr/bin/env python3
"""Recompute selected saved native transcripts and reject resealed substitutions.

This tool never acquires model responses. All process invocations use the fixed
external saved-transcript checker selected by the ONE adapter.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chimera_one import council_capture as c
from chimera_one.offline_review import ReviewError


def check(root, checkout, pins):
    return c.validate_council_capture(root=root, checkout=checkout, **pins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--chimera-checkout", type=Path, required=True)
    parser.add_argument("--expect-receipt", required=True)
    parser.add_argument("--expect-report", required=True)
    parser.add_argument("--expect-suite", required=True)
    parser.add_argument("--expect-model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pins = dict(expected_receipt=args.expect_receipt, expected_report=args.expect_report,
                expected_suite=args.expect_suite, expected_model=args.expect_model)
    positive = check(args.capture, args.chimera_checkout, pins)
    rejected = []

    def reject(name, root, selected):
        try:
            check(root, args.chimera_checkout, selected)
        except (ReviewError, ValueError):
            rejected.append(name)
        else:
            raise AssertionError("accepted saved-capture control: " + name)

    for key in pins:
        reject("wrong-" + key, args.capture, dict(pins, **{key: "sha256:" + "0" * 64}))
    changes = {
        "source-revision": lambda r: r["provider"].update(revision="0" * 40),
        "source-tree": lambda r: r["provider"].update(tree="0" * 40),
        "agi-promotion": lambda r: r["authority"].update(general_intelligence="CONFIRMED"),
        "boolean-process-exit": lambda r: r["invocation"].update(exit_code=False),
        "boolean-checker-exit": lambda r: r["invocation"].update(checker_exit_code=False),
        "incomplete-process": lambda r: r["invocation"].update(outcome="INCOMPLETE", exit_code=3),
        "external-host": lambda r: r["selection"].update(host="http://example.com:11434"),
    }
    original, _ = c.capture_bytes(args.capture, args.expect_receipt)
    with tempfile.TemporaryDirectory(prefix="one-council-saved-controls-") as temporary:
        def copy_capture(name):
            root = Path(temporary) / name
            shutil.copytree(args.capture, root)
            return root, copy.deepcopy(original)

        def reseal(root, receipt, selected):
            for name in c.FILE_LIMITS:
                raw = (root / name).read_bytes()
                receipt["artifacts"][name] = {"sha256": c.sha256(raw), "size_bytes": len(raw)}
            receipt["receipt_digest"] = c.receipt_digest(receipt)
            (root / "receipt.json").write_text(json.dumps(receipt))
            return dict(selected, expected_receipt=receipt["receipt_digest"])

        for name, mutate in changes.items():
            root, receipt = copy_capture(name)
            mutate(receipt)
            reject("rehashed-" + name, root, reseal(root, receipt, pins))
        for name, mutate in {
            "false-score": lambda r: r["summary"].update(single_exact_matches=999),
            "budget-increase": lambda r: r["budget"].update(max_generated_tokens_per_call=128),
            "trial-transplant": lambda r: r["results"][0].update(trial=2),
            "role-transplant": lambda r: r["results"][0]["single"]["trace"][0].update(agent="sample-3"),
        }.items():
            root, receipt = copy_capture(name)
            report = json.loads((root / "benchmark.json").read_bytes())
            mutate(report)
            report["report_digest"] = c.ag_digest("budget-benchmark/v2", {k: v for k, v in report.items() if k != "report_digest"})
            (root / "benchmark.json").write_text(json.dumps(report))
            receipt["report_digest"] = report["report_digest"]
            # Also reseal every outer reported summary/pin so that only the
            # external reconstruction of native transcripts can reject it.
            for artifact in ("provider.stdout", "checker.stdout"):
                value = json.loads((root / artifact).read_bytes())
                value.update(report_digest=report["report_digest"], summary=report["summary"])
                (root / artifact).write_text(json.dumps(value))
            selected = dict(pins, expected_report=report["report_digest"])
            reject("rehashed-" + name, root, reseal(root, receipt, selected))
        root, receipt = copy_capture("checker-transcript")
        (root / "checker.stdout").write_bytes((root / "checker.stdout").read_bytes() + b"\n")
        reject("rehashed-checker-transcript", root, reseal(root, receipt, pins))
        root, receipt = copy_capture("extra-file")
        (root / "unexpected").write_text("unselected")
        reject("unselected-extra-file", root, pins)

    value = {"status": "CONFORMANCE_PASSED", "validation": positive, "rejection_controls": rejected,
             "fresh_inference": "NOT_RUN", "scope": c.REPORT_SCOPE}
    with args.output.open("x") as target:
        json.dump(value, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"status": value["status"], "rejected": len(rejected)}))


if __name__ == "__main__":
    main()
