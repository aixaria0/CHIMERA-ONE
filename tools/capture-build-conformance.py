#!/usr/bin/env python3
"""Retained real native capture checks; optional full external artifact replay.

Private provider checkouts/artifacts are never fetched by this harness. Raw build
controls run only when all three caller-selected external paths are supplied.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from chimera_one import capture_build as build
from chimera_one import offline_review as review

FIXTURE = PROJECT / "examples/capture-build/native-replay"
PINS = {
    "expected_receipt": "sha256:8832edd572eb04f9cab4f24c082628a66f429dc93ef0945e7cf7025f9ee1861d",
    "expected_link": "sha256:499bad56abc83a7da78928d6557a6429eacfdbc4e60cee634f33d58a8f103419",
    "expected_binary": "3989b0b32395b21f1d33468e3af65225e36c22ea28fa7e931807bb8b02a54d10",
    "expected_controller": build.CHECKER_SHA256,
    "expected_left": "sha256:02249909a7fbd5e5007785b6f4ceb5621b6ad89a34c0f3d4669784e6b9ccad26",
    "expected_right": "sha256:c050c79699b77eb86afc11c9642d164f4ec364c487dcc1841ab3e1ab6714649a",
    "left_builder": "builder-a", "right_builder": "builder-b",
}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    for name in ("build-checkout", "left-build", "right-build"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    external = (args.build_checkout, args.left_build, args.right_build)
    if any(external) and not all(external):
        parser.error("full replay requires build-checkout, left-build and right-build together")
    args.out.mkdir(parents=True, exist_ok=False)
    capture = args.out / "capture"
    shutil.copytree(FIXTURE / "capture", capture)
    link = args.out / "build-link.json"
    original_link = review._bounded_read(FIXTURE / "build-link.json", build.MAX_LINK)
    link.write_bytes(original_link)
    original = json.loads(original_link)
    controls = []

    def validate(**overrides):
        return build.validate_capture_build(root=capture, link=link, **dict(PINS, **overrides))

    def reject(name, **overrides):
        try:
            validate(**overrides)
        except (review.ReviewError, OSError):
            controls.append(name)
        else:
            raise AssertionError("accepted build-link control: " + name)

    with patch.object(build, "_invoke", side_effect=AssertionError("retained validation ran a checker")), \
            patch.object(build, "_git", side_effect=AssertionError("retained validation inspected private source")):
        positive = validate()
        assert positive["raw_build_evidence_reverified"] == "NOT_RUN"
        for key in ("expected_receipt", "expected_link", "expected_binary", "expected_controller", "expected_left", "expected_right"):
            wrong = "0" * 64 if key in ("expected_binary", "expected_controller") else "sha256:" + "0" * 64
            reject("wrong-" + key, **{key: wrong})
        reject("wrong-left-builder", left_builder="wrong-a")
        reject("wrong-right-builder", right_builder="wrong-b")
        changes = {
            "capture-occurrence-transplant-with-rehash": lambda v: v["capture"].update(invocation_id="81c62c45-6c5e-4f32-9912-79df965a57a4"),
            "authority-extension-with-rehash": lambda v: v.update(authorized=True),
            "claim-promotion-with-rehash": lambda v: v["authority"].update(general_claim_verdict="CONFIRMED"),
            "build-record-transplant-with-rehash": lambda v: v["build_selection"].update(right_record_digest="sha256:" + "3" * 64),
        }
        for name, mutate in changes.items():
            value = copy.deepcopy(original)
            mutate(value)
            value["link_digest"] = build.link_digest(value)
            write(link, value)
            reject(name, expected_link=value["link_digest"])
        link.write_bytes(original_link + b" ")  # Whitespace is not a body mutation.
        validate()
        value = copy.deepcopy(original)
        value["checker_invocation"]["stdout_utf8"] = "{}"
        write(link, value)
        reject("checker-transcript-tampering-under-original-pin")
        link.write_bytes(original_link)
        stream = capture / "provider.stdout"
        saved = stream.read_bytes()
        stream.write_bytes(saved + b" ")
        reject("captured-provider-stream-substitution")
        stream.write_bytes(saved)
        validate()

    raw_controls, full = [], None
    if all(external):
        full = build.reverify_capture_build(root=capture, link=link, checker_checkout=args.build_checkout,
                                            left=args.left_build, right=args.right_build, **PINS)
        assert full["raw_build_evidence_reverified"] == "CONFIRMED"
        with tempfile.TemporaryDirectory(prefix="one-owned-raw-build-controls-") as temporary:
            root = Path(temporary)

            def raw_case(name, mutate, rehash_files=(), reseal=False):
                altered = root / name
                build._snapshot_build(args.right_build, altered)
                record = review._json(review._bounded_read(altered / "build.json", 32768))
                mutate(altered, record)
                for file_name in rehash_files:
                    data = (altered / file_name).read_bytes()
                    record["files"][file_name] = {"sha256": "sha256:" + review.sha256(data), "size": len(data)}
                selected = dict(PINS)
                selected.pop("expected_link")
                if reseal:
                    body = {k: v for k, v in record.items() if k != "record_digest"}
                    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
                    record["record_digest"] = "sha256:" + review.sha256(b"CHIMERA-OMEGA\0source-build-evidence/v1\0" + canonical)
                    selected["expected_right"] = record["record_digest"]
                write(altered / "build.json", record)
                output = root / (name + ".link.json")
                try:
                    build.bind_capture_build(root=capture, checker_checkout=args.build_checkout,
                                             left=args.left_build, right=altered, output=output, **selected)
                except review.ReviewError:
                    assert not output.exists()
                    raw_controls.append(name)
                else:
                    raise AssertionError("accepted raw build control: " + name)

            def binary_swap(path, _):
                for name in ("build-1/omega", "build-2/omega"):
                    member = path / name
                    member.write_bytes(member.read_bytes() + b"substituted")

            def source_swap(path, _):
                data = (path / "source.tar").read_bytes()
                stream = io.BytesIO()
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as source, tarfile.open(fileobj=stream, mode="w") as target:
                    for member in source:
                        target.addfile(member, source.extractfile(member) if member.isfile() else None)
                    member = tarfile.TarInfo("unreviewed-build-source.rs")
                    member.size = 6
                    target.addfile(member, io.BytesIO(b"attack"))
                (path / "source.tar").write_bytes(stream.getvalue())

            raw_case("fully-rehashed-binary-substitution", binary_swap, ("build-1/omega", "build-2/omega"), True)
            raw_case("fully-rehashed-source-substitution", source_swap, ("source.tar",), True)
            left_record = review._json(review._bounded_read(args.left_build / "build.json", 32768))
            raw_case("fully-rehashed-acquisition-reuse",
                     lambda _, r: r["acquisition"].update(occurrence=left_record["acquisition"]["occurrence"]), reseal=True)
            raw_case("fully-rehashed-tool-fingerprint-substitution",
                     lambda _, r: r["observed_tool_sha256"].update(rustc="sha256:" + "0" * 64), reseal=True)
            raw_case("raw-build-log-substitution", lambda p, _: (p / "build-1/stderr").write_bytes(b"invented build log"))

    write(args.out / "validation.json", positive)
    if full is not None:
        write(args.out / "raw-build-reverification.json", full)
    summary = {"status": "CONFORMANCE_PASSED", "saved_link_rejection_controls": controls,
               "raw_build_rejection_controls": raw_controls,
               "raw_build_evidence_reverified": "CONFIRMED" if full else "NOT_RUN",
               "provider_execution_reproduced": "NOT_RUN", "build_reexecution": "NOT_RUN",
               "target_runtime_reproduction": "NOT_RUN", "public_testnet_interaction": "NONE"}
    write(args.out / "controls.json", summary)
    write(args.out / "provenance.json", {"schema": "chimera-one-capture-build-conformance/v1", "selection": PINS,
                                         "acquisition_fixture_provenance_sha256": hashlib.sha256((FIXTURE / "provenance.json").read_bytes()).hexdigest(),
                                         **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
