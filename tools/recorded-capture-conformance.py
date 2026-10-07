#!/usr/bin/env python3
"""Verify a retained real capture; do not fetch or invoke the private provider."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from chimera_one import offline_review as review

PIN = "sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2"
FILES = ("inputs/export.json", "inputs/registry.json", "inputs/context.json",
         "provider.stdout", "provider.stderr", "receipt.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    original = PROJECT / "examples/offline-review/replay"
    root = args.out / "retained-replay"
    (root / "inputs").mkdir(parents=True)
    originals = {name: review._bounded_read(original / name) for name in FILES}
    for name, raw in originals.items():
        (root / name).write_bytes(raw)
    receipt = json.loads(originals["receipt.json"])
    controls = []

    def reject(name, pin):
        try:
            review.validate_capture(root, pin)
        except review.ReviewError:
            controls.append(name)
        else:
            raise AssertionError("capture substitution was accepted: " + name)

    # Keep this lane structurally incapable of invoking the provider through ONE.
    with patch.object(review, "_invoke", side_effect=AssertionError("recorded lane must not invoke OMEGA")):
        report = review.validate_capture(root, PIN)
        assert report["provider_execution_reproduced"] == "NOT_RUN"
        assert report["general_claim_verdict"] == "NOT_ASSESSED"
        reject("external receipt pin substitution", "sha256:" + "0" * 64)
        (root / "provider.stdout").write_bytes(originals["provider.stdout"] + b" ")
        reject("captured provider stream modification", PIN)
        (root / "provider.stdout").write_bytes(originals["provider.stdout"])

        changed = copy.deepcopy(receipt)
        changed["authority"]["source_build_binding"] = "CONFIRMED"
        changed["receipt_digest"] = review.receipt_digest(changed)
        write(root / "receipt.json", changed)
        reject("whole capture rehash under original pin", PIN)
        reject("authority promotion under fresh receipt pin", changed["receipt_digest"])
        (root / "receipt.json").write_bytes(originals["receipt.json"])

        changed = copy.deepcopy(receipt)
        raw = b'{"swapped":true}'
        (root / "inputs/export.json").write_bytes(raw)
        changed["inputs"]["export"] = review._artifact("inputs/export.json", raw)
        changed["receipt_digest"] = review.receipt_digest(changed)
        write(root / "receipt.json", changed)
        reject("input substitution under fresh receipt pin", changed["receipt_digest"])
        for name, raw in originals.items():
            (root / name).write_bytes(raw)
        review.validate_capture(root, PIN)

    assert originals == {name: review._bounded_read(original / name) for name in FILES}
    write(args.out / "capture-validation.json", report)
    write(args.out / "provenance.json", {
        "schema": "chimera-one-recorded-capture-conformance/v1",
        "mode": "RETAINED_CAPTURE_BYTES_ONLY", "expected_receipt": PIN,
        "fresh_provider_invocation": "NOT_RUN", "private_provider_checkout": "NOT_PERFORMED",
        "target_runtime_reproduction": "NOT_RUN", "public_testnet_interaction": "NONE",
        "underlying_capture_outcome": receipt["invocation"]["outcome"],
        "source_build_binding": "UNKNOWN", "rejection_controls": controls,
        "capture_acquisition": "Previously recorded real arm64 OMEGA invocation; see retained acquisition provenance.",
        "source_acquisition_provenance_sha256": sha(PROJECT / "examples/offline-review/provenance.json"),
        "artifact_sha256": {p.relative_to(args.out).as_posix(): sha(p)
                            for p in sorted(args.out.rglob("*")) if p.is_file()},
    })
    print(json.dumps({"status": "CONFORMANCE_PASSED", "mode": "RETAINED_CAPTURE_BYTES_ONLY",
                      "rejection_controls": len(controls), "fresh_provider_invocation": "NOT_RUN",
                      "private_provider_checkout": "NOT_PERFORMED", "public_testnet_interaction": "NONE"}))


if __name__ == "__main__":
    main()
