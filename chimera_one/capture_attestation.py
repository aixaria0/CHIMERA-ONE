"""Offline Ed25519 attribution of existing captures under explicit caller pins."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any

from .offline_review import (
    MAX_OUTPUT, ReviewError, _bounded_read, _invoke as _bounded_process,
    _json, sha256, validate_capture,
)
from .protocol import canonical_json

SCHEMA = "chimera-capture-attestation/v1"
STATEMENT_SCHEMA = "chimera-capture-statement/v1"
STATEMENT_SCOPE = "RECORDED_BYTES_MATCH_EXTERNALLY_PINNED_RECEIPT_ONLY"
ROLE = "CAPTURE_REVIEWER"
MAX_ATTESTATION = 8192
MAX_KEY = 8192
_PIN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_LABEL = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_PUBLIC = re.compile(r"[0-9a-f]{64}\Z")
_SIGNATURE = re.compile(r"[0-9a-f]{128}\Z")
# RFC 8410 SubjectPublicKeyInfo: Ed25519 OID, absent parameters, 32 raw bytes.
_SPKI = bytes.fromhex("302a300506032b6570032100")
_FILES = ("inputs/export.json", "inputs/registry.json", "inputs/context.json",
          "provider.stdout", "provider.stderr", "receipt.json")


def key_id(public_key: bytes) -> str:
    if len(public_key) != 32:
        raise ReviewError("Ed25519 public key must contain 32 bytes")
    return "sha256:" + sha256(public_key)


def signing_message(statement: dict[str, Any]) -> bytes:
    return b"CHIMERA-ONE\0capture/ed25519-statement/v1\0" + canonical_json(statement)


def attestation_digest(attestation: dict[str, Any]) -> str:
    body = dict(attestation)
    body.pop("attestation_digest", None)
    return "sha256:" + sha256(b"CHIMERA-ONE\0capture/attestation/v1\0" + canonical_json(body))


def _select(expected_receipt: str, expected_key: str, signer_id: str) -> None:
    if (not isinstance(expected_receipt, str) or not _PIN.fullmatch(expected_receipt)
            or not isinstance(expected_key, str) or not _PIN.fullmatch(expected_key)
            or not isinstance(signer_id, str) or not _LABEL.fullmatch(signer_id)):
        raise ReviewError("explicit lowercase receipt/key pins and a bounded signer label are required")


def _openssl() -> str:
    executable = shutil.which("openssl")
    if executable is None:
        raise ReviewError("OpenSSL 3 with Ed25519 pkeyutl support is required")
    # The host's Python and OpenSSL installations are trusted local verifier code,
    # not provider executables selected by a capability catalog or signed artifact.
    return str(Path(executable).resolve(strict=True))


def _crypto(executable: str, stage: Path, *arguments: str) -> bytes:
    try:
        code, stdout, _, reason = _bounded_process([executable, *arguments], stage)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReviewError("local Ed25519 operation unavailable") from exc
    if code != 0 or reason is not None:
        # Never return native diagnostics: a malformed key may contain secrets.
        raise ReviewError("local Ed25519 operation rejected")
    return stdout


def _snapshot(root: Path, stage: Path, expected: str) -> tuple[dict[str, Any], dict[str, Any]]:
    capture = stage / "capture"
    (capture / "inputs").mkdir(parents=True)
    for name in _FILES:
        limit = MAX_OUTPUT if name.startswith("provider.") else 1_048_576
        (capture / name).write_bytes(_bounded_read(root / name, limit))
    report = validate_capture(capture, expected)
    return _json(_bounded_read(capture / "receipt.json")), report


def _statement(receipt: dict[str, Any], public: bytes, signer_id: str) -> dict[str, Any]:
    return {"schema": STATEMENT_SCHEMA, "scope": STATEMENT_SCOPE, "role": ROLE,
            "signer_id": signer_id, "public_key": public.hex(), "key_id": key_id(public),
            "receipt_digest": receipt["receipt_digest"], "invocation_id": receipt["invocation_id"]}


def _secret(path: Path) -> bytes:
    # Refuse shared/foreign keys; read only bounded bytes into owned temporary state.
    # No passphrase, key generation, hidden key store or remote signer is provided.
    if os.name != "posix":
        raise ReviewError("capture signing currently requires a POSIX host")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path.resolve(strict=True), flags), "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077):
            raise ReviewError("signing key must be an owner-only regular local file")
        raw = handle.read(MAX_KEY + 1)
    if len(raw) > MAX_KEY:
        raise ReviewError("signing key exceeds its byte bound")
    return raw


def _private_file(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _verify_signature(executable: str, stage: Path, public: bytes,
                      message: bytes, signature: bytes) -> None:
    if len(signature) != 64:
        raise ReviewError("Ed25519 signature must contain 64 bytes")
    (stage / "public.der").write_bytes(_SPKI + public)
    (stage / "statement.bin").write_bytes(message)
    (stage / "signature.bin").write_bytes(signature)
    _crypto(executable, stage, "pkeyutl", "-verify", "-rawin", "-pubin", "-keyform", "DER",
            "-inkey", "public.der", "-in", "statement.bin", "-sigfile", "signature.bin")


def attest_capture(*, root: Path, expected_receipt: str, private_key: Path,
                   signer_id: str, expected_key: str, output: Path) -> dict[str, Any]:
    """Sign a validated snapshot; signing cannot authorize itself or rerun OMEGA."""
    _select(expected_receipt, expected_key, signer_id)
    root = root.resolve(strict=True)
    output = output.parent.resolve() / output.name
    if output.is_relative_to(root) or os.path.lexists(output):
        raise ReviewError("attestation must be a new file outside the original capture")
    if private_key.resolve(strict=True).is_relative_to(root):
        raise ReviewError("signing key must be kept outside the evidence capture")
    executable = _openssl()
    with tempfile.TemporaryDirectory(prefix="chimera-capture-sign-") as temporary:
        stage = Path(temporary)
        receipt, _ = _snapshot(root, stage, expected_receipt)
        _private_file(stage / "key.pem", _secret(private_key))
        public_der = _crypto(executable, stage, "pkey", "-in", "key.pem", "-passin", "pass:",
                             "-pubout", "-outform", "DER")
        if len(public_der) != len(_SPKI) + 32 or not public_der.startswith(_SPKI):
            raise ReviewError("signing key must use Ed25519 with the supported public-key encoding")
        public = public_der[len(_SPKI):]
        if key_id(public) != expected_key:
            raise ReviewError("external signer key pin mismatch")
        statement = _statement(receipt, public, signer_id)
        message = signing_message(statement)
        (stage / "statement.bin").write_bytes(message)
        signature = _crypto(executable, stage, "pkeyutl", "-sign", "-rawin",
                            "-inkey", "key.pem", "-passin", "pass:", "-in", "statement.bin")
        _verify_signature(executable, stage, public, message, signature)
        attestation = {"schema": SCHEMA, "algorithm": "Ed25519", "statement": statement,
                       "signature": signature.hex()}
        attestation["attestation_digest"] = attestation_digest(attestation)
        raw = canonical_json(attestation) + b"\n"
        if len(raw) > MAX_ATTESTATION:
            raise ReviewError("attestation exceeds its byte bound")
        output.parent.mkdir(parents=True, exist_ok=True)
        _private_file(output, raw)
    return {"schema": "chimera-capture-authoring-result/v1", "status": "SIGNED_NOT_AUTHORIZED",
            "scope": "OFFLINE_ED25519_CAPTURE_STATEMENT_ONLY", "receipt_digest": expected_receipt,
            "key_id": expected_key, "signer_id": signer_id,
            "attestation_digest": attestation["attestation_digest"], "attestation_path": str(output)}


def verify_capture_attestation(*, root: Path, attestation: Path, expected_receipt: str,
                               expected_key: str, expected_signer: str) -> dict[str, Any]:
    """Verify key attribution and saved bytes; preserve all non-cryptographic unknowns."""
    _select(expected_receipt, expected_key, expected_signer)
    value = _json(_bounded_read(attestation, MAX_ATTESTATION))
    if (not isinstance(value, dict)
            or set(value) != {"schema", "algorithm", "statement", "signature", "attestation_digest"}
            or value.get("schema") != SCHEMA or value.get("algorithm") != "Ed25519"
            or value.get("attestation_digest") != attestation_digest(value)):
        raise ReviewError("unsupported or modified capture attestation")
    statement = value["statement"]
    if (not isinstance(statement, dict) or not isinstance(statement.get("public_key"), str)
            or not _PUBLIC.fullmatch(statement["public_key"])
            or not isinstance(value["signature"], str) or not _SIGNATURE.fullmatch(value["signature"])):
        raise ReviewError("invalid Ed25519 statement or signature encoding")
    public = bytes.fromhex(statement["public_key"])
    if key_id(public) != expected_key:
        raise ReviewError("external signer key pin mismatch")
    executable = _openssl()
    with tempfile.TemporaryDirectory(prefix="chimera-capture-verify-") as temporary:
        stage = Path(temporary)
        receipt, report = _snapshot(root, stage, expected_receipt)
        if statement != _statement(receipt, public, expected_signer):
            raise ReviewError("signed statement differs from the selected capture, signer label or role")
        _verify_signature(executable, stage, public, signing_message(statement),
                          bytes.fromhex(value["signature"]))
    return {"schema": "chimera-capture-attestation-binding/v1", "status": "CONFIRMED",
            "scope": "PINNED_KEY_SIGNATURE_AND_SAVED_CAPTURE_BYTES_ONLY",
            "receipt_digest": expected_receipt, "attestation_digest": value["attestation_digest"],
            "key_id": expected_key, "signer_id": expected_signer,
            "signature_integrity": "CONFIRMED", "key_selection_binding": "CONFIRMED",
            "signer_label_binding": "CONFIRMED", "capture_validation": report,
            "policy_authorization": "NOT_ASSESSED", "signer_identity": "UNKNOWN",
            "independent_observation": "UNKNOWN", "process_independence": "UNKNOWN",
            "source_build_binding": "UNKNOWN", "freshness": "UNKNOWN", "key_revocation": "UNKNOWN",
            "provider_execution_reproduced": "NOT_RUN", "general_claim_verdict": "NOT_ASSESSED"}
