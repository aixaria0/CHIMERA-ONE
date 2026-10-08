"""Join a saved capture to explicitly selected external OMEGA build evidence.

The small adapter never imports the provider source tree. Saved-link validation
and raw external build re-verification have deliberately different reports.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Any

from .capture_attestation import _snapshot as _capture_snapshot, _private_file
from .offline_review import (
    OMEGA_REPOSITORY, OMEGA_REVISION, OMEGA_TREE, ReviewError,
    _bounded_read, _git, _hex, _invoke, _json, sha256,
)
from .protocol import canonical_json

SCHEMA = "chimera-capture-build-link/v1"
SCOPE = "CAPTURE_SELECTED_BINARY_AND_SOURCE_TO_PINNED_SAVED_BUILD_EVIDENCE_ONLY"
CHECKER_REVISION = "9ab2390364fd8c89f29fa46569b58d33ddb61869"
CHECKER_TREE = "d80c482dc2a6e20ba4e2cc56217b773772b61610"
CHECKER_PATH = "tools/omega-build-evidence.py"
CHECKER_SHA256 = "40346dd9adac3c22401cfd9a83a729c164d2951f2baf692bf74b4316f78caff1"
MAX_LINK = 16384
_PIN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_LABEL = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
BUILD_FILES = {
    "build.json": 32768, "source.tar": 8 * 1024 * 1024, "source.commit": 32768,
    "controller.py": 131072, "rustc.txt": 32768, "cargo.txt": 32768,
    "fetch.stdout": 1048576, "fetch.stderr": 1048576,
    "build-1/omega": 16 * 1024 * 1024, "build-2/omega": 16 * 1024 * 1024,
    "build-1/stdout": 1048576, "build-1/stderr": 1048576,
    "build-2/stdout": 1048576, "build-2/stderr": 1048576,
}
AUTHORITY = {
    "build_execution": "ATTRIBUTED_NOT_ATTESTED", "toolchain_closure": "UNKNOWN",
    "compiler_correctness": "UNKNOWN", "independent_observation": "UNKNOWN",
    "organizational_independence": "UNKNOWN", "hardware_independence": "UNKNOWN",
    "freshness": "UNKNOWN", "signature_integrity": "NOT_ASSESSED",
    "signer_authorization": "NOT_ASSESSED", "general_claim_verdict": "NOT_ASSESSED",
    "provider_execution_reproduced": "NOT_RUN", "build_reexecution": "NOT_RUN",
    "target_runtime_reproduction": "NOT_RUN", "os_network_sandbox": "NOT_ESTABLISHED",
}


def link_digest(value: dict[str, Any]) -> str:
    body = dict(value)
    body.pop("link_digest", None)
    return "sha256:" + sha256(b"CHIMERA-ONE\0capture/build-link/v1\0" + canonical_json(body))


def select(*, expected_receipt: str, expected_binary: str, expected_controller: str,
           expected_left: str, expected_right: str, left_builder: str, right_builder: str) -> dict[str, str]:
    if (not all(isinstance(v, str) and _PIN.fullmatch(v) for v in
                (expected_receipt, expected_left, expected_right))
            or not _hex(expected_binary) or not _hex(expected_controller)
            or expected_controller != CHECKER_SHA256
            or not all(isinstance(v, str) and _LABEL.fullmatch(v) for v in (left_builder, right_builder))
            or left_builder == right_builder or expected_left == expected_right):
        raise ReviewError("separate explicit receipt/build pins, supported controller and distinct builder labels are required")
    return {"source_revision": OMEGA_REVISION, "source_tree": OMEGA_TREE,
            "binary_sha256": expected_binary, "controller_sha256": expected_controller,
            "left_record_digest": expected_left, "right_record_digest": expected_right,
            "left_builder": left_builder, "right_builder": right_builder}


def _comparison(selection: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": "chimera-omega/source-build-comparison/v1",
        "status": "PINNED_SAVED_SOURCE_AND_BINARY_BYTES_MATCH",
        "scope": "TWO_ATTRIBUTED_ACQUISITIONS_WITH_TWO_FRESH_BUILDS_EACH",
        "records": [selection["left_record_digest"], selection["right_record_digest"]],
        "source_revision": OMEGA_REVISION, "source_tree": OMEGA_TREE,
        "binary_sha256": "sha256:" + selection["binary_sha256"],
        "dimensions": {
            "saved_source_git_object_binding": "CONFIRMED", "saved_binary_agreement": "CONFIRMED",
            "build_execution": "ATTRIBUTED_NOT_ATTESTED", "ci_declarations": "NOT_AUTHENTICATED_BY_THIS_VERIFIER",
            "organizational_independence": "UNKNOWN", "hardware_independence": "UNKNOWN",
            "compiler_correctness": "UNKNOWN", "historical_capture_binary_binding": "NOT_ASSESSED",
            "freshness": "UNKNOWN", "general_claim": "NOT_ASSESSED", "target_execution": "NOT_RUN",
        },
    }


def _checker_identity() -> dict[str, str]:
    return {"repository": OMEGA_REPOSITORY, "revision": CHECKER_REVISION, "tree": CHECKER_TREE,
            "path": CHECKER_PATH, "sha256": CHECKER_SHA256}


def inspect_checker(checkout: Path) -> bytes:
    origin = _git(checkout, "remote", "get-url", "origin")
    if origin.startswith("git@github.com:"):
        origin = "https://github.com/" + origin[len("git@github.com:"):]
    if (_git(checkout, "rev-parse", "HEAD") != CHECKER_REVISION
            or _git(checkout, "rev-parse", "HEAD^{tree}") != CHECKER_TREE
            or origin.removesuffix(".git").rstrip("/") != "https://github.com/" + OMEGA_REPOSITORY
            or _git(checkout, "status", "--porcelain")):
        raise ReviewError("build-checker revision, tree, ownership origin or cleanliness mismatch")
    raw = _bounded_read(checkout / CHECKER_PATH, 131072)
    if sha256(raw) != CHECKER_SHA256:
        raise ReviewError("build-checker code differs from the supported external controller pin")
    return raw


def _members(path: Path) -> set[str]:
    if path.is_symlink() or not path.is_dir():
        raise ReviewError("build artifacts must be regular directories without symlinks")
    result: set[str] = set()
    with os.scandir(path) as entries:
        for entry in entries:
            result.add(entry.name)
            if len(result) > 16 or entry.is_symlink():
                raise ReviewError("unsupported build artifact membership")
    return result


def _read_build(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ReviewError("build artifact type/size limit")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ReviewError("build artifact exceeds byte bound")
    return raw


def _snapshot_build(source: Path, destination: Path) -> None:
    top = {name for name in BUILD_FILES if "/" not in name} | {"build-1", "build-2"}
    if (_members(source) != top or any(_members(source / child) != {"omega", "stdout", "stderr"}
                                       for child in ("build-1", "build-2"))):
        raise ReviewError("build artifact membership differs from supported contract")
    destination.mkdir(mode=0o700)
    for child in ("build-1", "build-2"):
        (destination / child).mkdir(mode=0o700)
    for name, limit in BUILD_FILES.items():
        (destination / name).write_bytes(_read_build(source / name, limit))


def _check_builds(stage: Path, checkout: Path, left: Path, right: Path,
                  selection: dict[str, str]) -> dict[str, Any]:
    raw = inspect_checker(checkout.resolve(strict=True))
    script = stage / "selected-checker.py"
    script.write_bytes(raw)
    script.chmod(0o400)
    _snapshot_build(left, stage / "left")
    _snapshot_build(right, stage / "right")
    command = [sys.executable, "-I", "-B", str(script), "compare", "--left", "left", "--right", "right",
               "--expect-source", OMEGA_REVISION, "--expect-tree", OMEGA_TREE,
               "--expect-binary", "sha256:" + selection["binary_sha256"],
               "--expect-controller", "sha256:" + selection["controller_sha256"],
               "--expect-left", selection["left_record_digest"], "--expect-right", selection["right_record_digest"],
               "--left-builder", selection["left_builder"], "--right-builder", selection["right_builder"]]
    code, stdout, stderr, reason = _invoke(command, stage)
    if (code != 0 or reason is not None or stderr
            or canonical_json(_json(stdout)) != canonical_json(_comparison(selection))):
        raise ReviewError("pinned external saved-build verification rejected or changed its scope")
    return {"exit_code": 0, "stdout_utf8": stdout.decode("utf-8"), "stderr_utf8": ""}


def _capture_reference(receipt: dict[str, Any], expected_receipt: str, selection: dict[str, str]) -> dict[str, Any]:
    if receipt["receipt_digest"] != expected_receipt or receipt["binary_sha256"] != selection["binary_sha256"]:
        raise ReviewError("capture selected binary differs from externally selected build binary")
    return {"receipt_digest": expected_receipt, "invocation_id": receipt["invocation_id"],
            "provider": receipt["provider"], "binary_sha256": receipt["binary_sha256"],
            "provider_outcome": receipt["invocation"]["outcome"]}


def bind_capture_build(*, root: Path, checker_checkout: Path, left: Path, right: Path,
                       output: Path, expected_receipt: str, **pins: str) -> dict[str, Any]:
    selection = select(expected_receipt=expected_receipt, **pins)
    root = root.resolve(strict=True)
    output = output.parent.resolve() / output.name
    protected = (root, checker_checkout.resolve(strict=True), left.resolve(strict=True), right.resolve(strict=True))
    if os.path.lexists(output) or any(output.is_relative_to(path) for path in protected):
        raise ReviewError("build link must be a new file outside capture, checker and build artifacts")
    with tempfile.TemporaryDirectory(prefix="chimera-capture-build-") as temporary:
        stage = Path(temporary)
        receipt, _ = _capture_snapshot(root, stage, expected_receipt)
        reference = _capture_reference(receipt, expected_receipt, selection)
        invocation = _check_builds(stage, checker_checkout, left, right, selection)
        value = {"schema": SCHEMA, "status": "RECORDED_BUILD_EVIDENCE_CHECK", "scope": SCOPE,
                 "capture": reference, "build_selection": selection, "checker": _checker_identity(),
                 "checker_invocation": invocation, "comparison": _comparison(selection), "authority": dict(AUTHORITY)}
        value["link_digest"] = link_digest(value)
        raw = canonical_json(value) + b"\n"
        if len(raw) > MAX_LINK:
            raise ReviewError("build link exceeds byte bound")
        output.parent.mkdir(parents=True, exist_ok=True)
        _private_file(output, raw)
    return {"status": "RECORDED_NOT_AUTHORIZED", "link_digest": value["link_digest"],
            "receipt_digest": expected_receipt, "provider_outcome": reference["provider_outcome"],
            "build_execution": "ATTRIBUTED_NOT_ATTESTED", "output": str(output)}


def validate_capture_build(*, root: Path, link: Path, expected_link: str,
                           expected_receipt: str, **pins: str) -> dict[str, Any]:
    """Validate pinned saved link bytes. No subprocess, compiler or provider run."""
    selection = select(expected_receipt=expected_receipt, **pins)
    if not isinstance(expected_link, str) or not _PIN.fullmatch(expected_link):
        raise ReviewError("explicit external build-link pin required")
    value = _json(_bounded_read(link, MAX_LINK))
    if (not isinstance(value, dict) or value.get("link_digest") != expected_link
            or link_digest(value) != expected_link):
        raise ReviewError("external build-link pin mismatch")
    with tempfile.TemporaryDirectory(prefix="chimera-build-link-validate-") as temporary:
        receipt, capture_report = _capture_snapshot(root, Path(temporary), expected_receipt)
        invocation = value.get("checker_invocation")
        if (not isinstance(invocation, dict) or set(invocation) != {"exit_code", "stdout_utf8", "stderr_utf8"}
                or type(invocation["exit_code"]) is not int or invocation["exit_code"] != 0
                or not isinstance(invocation["stdout_utf8"], str) or invocation["stderr_utf8"] != ""
                or canonical_json(_json(invocation["stdout_utf8"].encode())) != canonical_json(_comparison(selection))):
            raise ReviewError("unsupported saved build-checker invocation")
        expected = {"schema": SCHEMA, "status": "RECORDED_BUILD_EVIDENCE_CHECK", "scope": SCOPE,
                    "capture": _capture_reference(receipt, expected_receipt, selection), "build_selection": selection,
                    "checker": _checker_identity(), "checker_invocation": invocation,
                    "comparison": _comparison(selection), "authority": dict(AUTHORITY), "link_digest": expected_link}
        if canonical_json(value) != canonical_json(expected):
            raise ReviewError("saved build link differs from selected capture, builds or authority boundary")
    return {"schema": "chimera-capture-build-validation/v1", "status": "CONFIRMED", "scope": SCOPE,
            "mode": "SAVED_CAPTURE_AND_ATTRIBUTED_BUILD_REPORT_ONLY", "link_digest": expected_link,
            "receipt_digest": expected_receipt, "capture_validation": capture_report,
            "binary_digest_to_selected_build_report": "CONFIRMED", "raw_build_evidence_reverified": "NOT_RUN",
            **AUTHORITY}


def reverify_capture_build(*, root: Path, link: Path, checker_checkout: Path, left: Path, right: Path,
                          expected_link: str, expected_receipt: str, **pins: str) -> dict[str, Any]:
    """Repeat offline external source/tree/binary checks, never builds or OMEGA."""
    report = validate_capture_build(root=root, link=link, expected_link=expected_link,
                                   expected_receipt=expected_receipt, **pins)
    selection = select(expected_receipt=expected_receipt, **pins)
    with tempfile.TemporaryDirectory(prefix="chimera-build-reverify-") as temporary:
        invocation = _check_builds(Path(temporary), checker_checkout, left, right, selection)
    value = _json(_bounded_read(link, MAX_LINK))
    if (value.get("link_digest") != expected_link or link_digest(value) != expected_link
            or canonical_json(invocation) != canonical_json(value["checker_invocation"])):
        raise ReviewError("reverified build-checker transcript differs from externally pinned saved link")
    return {**report, "mode": "REVERIFIED_EXTERNAL_SAVED_SOURCE_AND_BINARY_BYTES",
            "raw_build_evidence_reverified": "CONFIRMED"}
