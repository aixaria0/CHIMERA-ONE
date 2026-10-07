"""One explicitly selected, offline OMEGA invocation; no general plan executor."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from typing import Any
import uuid

from .protocol import canonical_json

OMEGA_REPOSITORY = "aixaria0/CHIMERA-OMEGA"
OMEGA_REVISION = "52a21a8eaa4363d648fdac805900175d81e13f07"
OMEGA_TREE = "ddb6a6b8ee60ee0ac5b865a69a8a60bf0cf06c0e"
OMEGA_MANIFEST_SHA256 = "d5d1ec1e80249ba607dcffdd13d8e6baf4413b8277cbce64a71efe59decbfde3"
CAPABILITY = "omega.verify-aether-historical-journal"
REPORT_SCHEMA = "chimera-aether-historical-journal-binding/v1"
REPORT_SCOPE = "EXACT_RECEIPT_REGISTRY_AUTHORIZATION_AND_PINNED_COMPLETE_JOURNAL_ONLY"
MAX_INPUT = 1_048_576
MAX_BINARY = 67_108_864
MAX_OUTPUT = 131_072
TIMEOUT_SECONDS = 10.0
_INPUTS = ("export", "registry", "context")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_AUTHORITY = {
    "provider_report": "ATTRIBUTED_PROVIDER_REPORT",
    "capture_integrity": "CONTENT_ADDRESSED_ONLY",
    "source_build_binding": "UNKNOWN",
    "process_independence": "UNKNOWN",
    "target_runtime_reproduction": "NOT_RUN",
    "general_claim_verdict": "NOT_ASSESSED",
    "network_policy": "SUPPORTED_OFFLINE_VERIFIER_ONLY",
    "os_network_sandbox": "NOT_ESTABLISHED",
}


class ReviewError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def _open_regular(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path.resolve(strict=True), flags)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ReviewError("artifact must be a regular local file")
    return os.fdopen(descriptor, "rb")


def _bounded_read(path: Path, limit: int = MAX_INPUT) -> bytes:
    with _open_regular(path) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ReviewError("artifact exceeds its byte bound")
    return data


def _json(data: bytes) -> Any:
    # Bound recursion before json.loads, including syntactically invalid inputs.
    depth, quoted, escaped = 0, False, False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > 32:
                raise ReviewError("JSON depth exceeds 32")
        elif byte in (93, 125):
            depth = max(0, depth - 1)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result or not key.isascii() or len(key) > 128:
                raise ReviewError("duplicate or unsupported JSON object key")
            result[key] = value
        return result

    def unsupported(_: str) -> Any:
        raise ReviewError("unsupported JSON number")

    def integer(text: str) -> int:
        value = int(text)
        if not 0 <= value <= 9_007_199_254_740_991:
            raise ReviewError("unsafe JSON integer")
        return value

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_float=unsupported, parse_constant=unsupported,
                           parse_int=integer)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ReviewError("invalid bounded JSON") from exc

    def check_strings(item: Any) -> None:
        if isinstance(item, str) and len(item.encode("utf-8")) > 4096:
            raise ReviewError("JSON string exceeds 4096 bytes")
        if isinstance(item, list):
            for child in item:
                check_strings(child)
        elif isinstance(item, dict):
            for child in item.values():
                check_strings(child)
    try:
        check_strings(value)
    except UnicodeError as exc:
        raise ReviewError("invalid Unicode string") from exc
    return value


def omega_digest(domain: str, value: Any) -> str:
    return sha256(b"CHIMERA-OMEGA\0" + domain.encode() + b"\0" + canonical_json(value))


def receipt_digest(value: dict[str, Any]) -> str:
    body = dict(value)
    body.pop("receipt_digest", None)
    return "sha256:" + sha256(b"chimera-offline-review/v1\0" + canonical_json(body))


def _git(checkout: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                           "-c", "core.hooksPath=/dev/null", "-C", str(checkout), *args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, timeout=5, check=False)
    if proc.returncode or len(proc.stdout) > MAX_OUTPUT:
        raise ReviewError("cannot inspect the selected local provider checkout")
    return proc.stdout.decode("utf-8").strip()


def inspect_provider(checkout: Path) -> dict[str, Any]:
    head = _git(checkout, "rev-parse", "HEAD")
    tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    origin = _git(checkout, "remote", "get-url", "origin")
    if origin.startswith("git@github.com:"):
        origin = "https://github.com/" + origin[len("git@github.com:"):]
    if (head != OMEGA_REVISION or tree != OMEGA_TREE
            or origin.removesuffix(".git").rstrip("/") != "https://github.com/" + OMEGA_REPOSITORY
            or _git(checkout, "status", "--porcelain")):
        raise ReviewError("provider revision, tree, ownership origin or cleanliness mismatch")
    raw = _bounded_read(checkout / "chimera.provider.json")
    if sha256(raw) != OMEGA_MANIFEST_SHA256:
        raise ReviewError("provider manifest bytes differ from the supported source pin")
    manifest = _json(raw)
    if not isinstance(manifest, dict):
        raise ReviewError("invalid provider manifest")
    selected = [e for e in manifest.get("entrypoints", [])
                if isinstance(e, dict) and e.get("capability") == CAPABILITY]
    if (manifest.get("repository") != OMEGA_REPOSITORY
            or manifest.get("control_plane") != "aixaria0/CHIMERA-ONE"
            or len(selected) != 1
            or any(selected[0].get(k) != v for k, v in
                   {"mode": "verification", "network": "none", "mutation": "none"}.items())):
        raise ReviewError("provider does not declare the supported offline contract")
    return {"repository": OMEGA_REPOSITORY, "revision": head, "tree": tree,
            "manifest_sha256": sha256(raw)}


def _command(binary: str, inputs: dict[str, str], expected: str) -> list[str]:
    return [binary, "verify-aether-historical-journal", inputs["export"], "--registry",
            inputs["registry"], "--context", inputs["context"], "--expect-context", expected]


def _invoke(command: list[str], cwd: Path) -> tuple[int | None, bytes, bytes, str | None]:
    if os.name != "posix":
        raise ReviewError("bounded invocation currently requires a POSIX host")
    # The supported OMEGA command performs no network I/O. This is not an OS sandbox.
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    outputs = [bytearray(), bytearray()]
    reason: str | None = None
    deadline = time.monotonic() + TIMEOUT_SECONDS
    with selectors.DefaultSelector() as selector:
        assert proc.stdout is not None and proc.stderr is not None
        for i, stream in enumerate((proc.stdout, proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, i)
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    reason = "provider timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    data = os.read(key.fd, 16384)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    target = outputs[key.data]
                    capacity = MAX_OUTPUT - len(target)
                    target.extend(data[:capacity])
                    if len(data) > capacity:
                        reason = "provider output exceeds byte bound"
                        break
                if reason:
                    break
            if reason is None:
                try:
                    proc.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    reason = "provider timeout"
        finally:
            # Stop only the process group owned by this invocation, including
            # children holding pipes or outliving the reviewed provider process.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=2)
            proc.stdout.close()
            proc.stderr.close()
    if reason is None and proc.returncode < 0:
        reason = f"provider terminated by signal {abs(proc.returncode)}"
    return proc.returncode if reason is None else None, bytes(outputs[0]), bytes(outputs[1]), reason


def _outcome(stdout: bytes, exit_code: int | None, context: dict[str, Any], inputs: dict[str, Any]) -> tuple[str, Any, str | None]:
    if type(exit_code) is not int or exit_code not in (0, 2):
        return "BLOCKED", None, "unexpected provider exit"
    try:
        report = _json(stdout)
        if not isinstance(report, dict):
            raise ReviewError("provider report is not an object")
        if exit_code == 2:
            if report.get("status") != "REJECTED":
                raise ReviewError("provider exit/report disagreement")
            return "REJECTED", report, None
        certificate = inputs["export"]["lineage"]["certificate"]
        if (context.get("journal_export_digest") != omega_digest("aether/journal-export/v1", inputs["export"])
                or context.get("registry_digest") != omega_digest("aether/historical-registry/v1", inputs["registry"])
                or context.get("certificate_digest") != omega_digest("aether/lattice-certificate/v1", certificate)):
            raise ReviewError("provider success is not bound to the captured input snapshots")
        expected = {"schema": REPORT_SCHEMA, "scope": REPORT_SCOPE, "status": "CONFIRMED",
                    "context_digest": omega_digest("aether/historical-context/v1", context),
                    "source_repository": "aixaria0/aether-runtime",
                    "lineage_source_revision": "04d785f7beee5ff96d78e092a1d73b79987c9e0e",
                    "journal_export_source_revision": "30dad8ec794e3f27600bfc0a5a5df072e79ba8c4",
                    "registry_freshness": "UNKNOWN", "historical_time_authorization": "UNKNOWN",
                    "current_live_key_authorization": "UNKNOWN", "external_journal_anchor": "UNKNOWN",
                    "independent_observation": "UNKNOWN", "producer_binary_attestation": "UNKNOWN",
                    "runtime_reproduction": "NOT_RUN", "omega_core_verdict": "NOT_RUN"}
        for field in ("registry_digest", "journal_export_digest", "certificate_digest",
                      "journal_head_sha256", "journal_event_count"):
            expected[field] = context.get(field)
        for field in ("signature_integrity", "raw_operation_binding", "selected_policy_binding",
                      "registry_authorization_binding", "journal_chain_integrity",
                      "journal_sequence_integrity", "receipt_event_binding"):
            expected[field] = "CONFIRMED"
        if any(report.get(k) != v for k, v in expected.items()):
            raise ReviewError("provider report changed scope, selected evidence or authority dimensions")
        if (report.get("direct_replay_binding") not in ("CONFIRMED", "NOT_APPLICABLE")
                or report.get("parent_receipt_event_binding") != report.get("direct_replay_binding")
                or not isinstance(report.get("producer_view"), dict)
                or report["producer_view"].get("authority") != "ATTRIBUTED_ONLY"):
            raise ReviewError("provider omitted the direct-parent or producer-attribution boundary")
        return "CONFIRMED", report, None
    except (ReviewError, KeyError, TypeError, AttributeError):
        return "BLOCKED", None, "invalid or unsupported provider report"


def _artifact(name: str, data: bytes) -> dict[str, Any]:
    return {"path": name, "sha256": sha256(data), "size_bytes": len(data)}


def _write_receipt(root: Path, receipt: dict[str, Any]) -> None:
    (root / "receipt.json").write_bytes(json.dumps(receipt, indent=2, sort_keys=True,
                                                 ensure_ascii=False).encode() + b"\n")


def review_aether_history(*, checkout: Path, binary: Path, expected_binary: str,
                         export: Path, registry: Path, context: Path,
                         expected_context: str, output: Path) -> dict[str, Any]:
    if not _hex(expected_binary) or not _hex(expected_context):
        raise ReviewError("explicit lowercase binary and context SHA-256 pins are required")
    source = inspect_provider(checkout.resolve(strict=True))
    inputs = {name: _bounded_read(path) for name, path in
              zip(_INPUTS, (export, registry, context))}
    parsed = {name: _json(raw) for name, raw in inputs.items()}
    selected = parsed["context"]
    if not isinstance(selected, dict) or omega_digest("aether/historical-context/v1", selected) != expected_context:
        raise ReviewError("external historical context pin mismatch")
    output = output.parent.resolve() / output.name
    if output.is_relative_to(checkout.resolve()) or os.path.lexists(output):
        raise ReviewError("capture output must be a new directory outside the provider checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".chimera-offline-review-", dir=output.parent) as tmp:
        stage = Path(tmp)
        executable = stage / "omega-reviewed"
        digest = hashlib.sha256()
        size = 0
        with _open_regular(binary) as src, executable.open("xb") as dst:
            while data := src.read(131072):
                size += len(data)
                if size > MAX_BINARY:
                    raise ReviewError("reviewed executable exceeds byte bound")
                digest.update(data)
                dst.write(data)
        if digest.hexdigest() != expected_binary:
            raise ReviewError("reviewed executable SHA-256 mismatch")
        executable.chmod(0o500)
        folder = stage / "invocation"
        (folder / "inputs").mkdir(parents=True)
        for name, raw in inputs.items():
            (folder / "inputs" / f"{name}.json").write_bytes(raw)
        paths = {name: f"inputs/{name}.json" for name in _INPUTS}
        command = _command(str(executable), paths, expected_context)
        exit_code, stdout, stderr, reason = _invoke(command, folder)
        try:
            unchanged = all(_bounded_read(folder / paths[name]) == raw for name, raw in inputs.items())
        except (OSError, ReviewError):
            unchanged = False
        if not unchanged:
            reason = "provider changed an input snapshot"
        if reason is None:
            outcome, report, reason = _outcome(stdout, exit_code, selected, parsed)
        else:
            outcome, report = "BLOCKED", None
        # Seal fresh originals after the provider group has stopped. A changed or
        # deleted invocation snapshot never replaces the original captured bytes.
        folder = stage / "bundle"
        (folder / "inputs").mkdir(parents=True)
        for name, raw in inputs.items():
            (folder / paths[name]).write_bytes(raw)
        (folder / "provider.stdout").write_bytes(stdout)
        (folder / "provider.stderr").write_bytes(stderr)
        receipt: dict[str, Any] = {
            "schema": "chimera-offline-review/v1", "status": "RECORDED_PROVIDER_INVOCATION",
            "invocation_id": str(uuid.uuid4()), "capability": CAPABILITY,
            "control_plane": {"repository": "aixaria0/CHIMERA-ONE",
                              "source_snapshot": "DISK_SOURCE_BYTES_ONLY",
                              "source_sha256": {name: sha256(_bounded_read(Path(__file__).parent / name))
                                                for name in ("offline_review.py", "cli.py", "protocol.py")}},
            "provider": source, "binary_sha256": expected_binary,
            "expected_context_sha256": expected_context,
            "limits": {"max_input_bytes": MAX_INPUT, "max_binary_bytes": MAX_BINARY,
                       "max_stream_bytes": MAX_OUTPUT, "timeout_ms": int(TIMEOUT_SECONDS * 1000)},
            "inputs": {name: _artifact(paths[name], raw) for name, raw in inputs.items()},
            "invocation": {"command": _command("<reviewed-omega-binary>", paths, expected_context),
                           "exit_code": exit_code, "outcome": outcome, "reason": reason,
                           "input_snapshots_unchanged": unchanged,
                           "stdout": _artifact("provider.stdout", stdout),
                           "stderr": _artifact("provider.stderr", stderr)},
            "provider_report": report, "authority": copy.deepcopy(_AUTHORITY),
        }
        receipt["receipt_digest"] = receipt_digest(receipt)
        _write_receipt(folder, receipt)
        # An exclusive mkdir protects existing bundles; only this owned output is
        # removed if a copy fails. No repository or pre-existing output is replaced.
        output.mkdir(mode=0o700)
        try:
            # Copy bounded evidence bytes only. Source metadata/xattrs neither
            # establish evidence authority nor port reliably across UserLAnd.
            (output / "inputs").mkdir(mode=0o700)
            for name in (*paths.values(), "provider.stdout", "provider.stderr", "receipt.json"):
                (output / name).write_bytes(_bounded_read(folder / name))
        except BaseException:
            shutil.rmtree(output)
            raise
    return receipt


def validate_capture(root: Path, expected_receipt: str) -> dict[str, Any]:
    receipt = _json(_bounded_read(root / "receipt.json"))
    if not isinstance(receipt, dict) or expected_receipt != receipt_digest(receipt) or receipt.get("receipt_digest") != expected_receipt:
        raise ReviewError("external capture receipt pin mismatch")
    if (receipt.get("schema") != "chimera-offline-review/v1"
            or receipt.get("status") != "RECORDED_PROVIDER_INVOCATION"
            or receipt.get("capability") != CAPABILITY or receipt.get("authority") != _AUTHORITY):
        raise ReviewError("unsupported capture contract")
    if set(receipt) != {"schema", "status", "invocation_id", "capability", "control_plane", "provider", "limits",
                        "binary_sha256", "expected_context_sha256", "inputs", "invocation",
                        "provider_report", "authority", "receipt_digest"}:
        raise ReviewError("unsupported capture fields")
    provider = receipt.get("provider", {})
    if (not isinstance(provider, dict) or set(provider) != {"repository", "revision", "tree", "manifest_sha256"}
            or provider.get("repository") != OMEGA_REPOSITORY or provider.get("revision") != OMEGA_REVISION
            or provider.get("tree") != OMEGA_TREE or provider.get("manifest_sha256") != OMEGA_MANIFEST_SHA256
            or not _hex(receipt.get("binary_sha256")) or not _hex(receipt.get("expected_context_sha256"))):
        raise ReviewError("unsupported captured provider selection")
    try:
        control_plane = receipt["control_plane"]
        if (set(control_plane) != {"repository", "source_snapshot", "source_sha256"}
                or control_plane["repository"] != "aixaria0/CHIMERA-ONE"
                or control_plane["source_snapshot"] != "DISK_SOURCE_BYTES_ONLY"
                or set(control_plane["source_sha256"]) != {"offline_review.py", "cli.py", "protocol.py"}
                or not all(_hex(h) for h in control_plane["source_sha256"].values())):
            raise ReviewError("invalid control-plane source declaration")
        limits = receipt["limits"]
        if (set(limits) != {"max_input_bytes", "max_binary_bytes", "max_stream_bytes", "timeout_ms"}
                or not all(type(n) is int for n in limits.values())
                or limits["max_input_bytes"] != MAX_INPUT or limits["max_binary_bytes"] != MAX_BINARY
                or limits["max_stream_bytes"] != MAX_OUTPUT or not 1 <= limits["timeout_ms"] <= 10000):
            raise ReviewError("invalid captured invocation bounds")
        uuid.UUID(receipt["invocation_id"])
        paths = {name: f"inputs/{name}.json" for name in _INPUTS}
        inputs = {}
        for name, path in paths.items():
            raw = _bounded_read(root / path)
            if receipt["inputs"][name] != _artifact(path, raw):
                raise ReviewError("captured input bytes mismatch")
            inputs[name] = _json(raw)
        context = inputs["context"]
        if omega_digest("aether/historical-context/v1", context) != receipt["expected_context_sha256"]:
            raise ReviewError("captured historical context pin mismatch")
        invocation = receipt["invocation"]
        if invocation["command"] != _command("<reviewed-omega-binary>", paths, receipt["expected_context_sha256"]):
            raise ReviewError("captured invocation contract mismatch")
        streams = {}
        for name in ("stdout", "stderr"):
            path = f"provider.{name}"
            raw = _bounded_read(root / path, MAX_OUTPUT)
            if invocation[name] != _artifact(path, raw):
                raise ReviewError("captured provider stream mismatch")
            streams[name] = raw
        if invocation["outcome"] == "BLOCKED":
            if not invocation["reason"] or receipt["provider_report"] is not None:
                raise ReviewError("inconsistent blocked capture")
        else:
            outcome, report, reason = _outcome(streams["stdout"], invocation["exit_code"], context, inputs)
            if (outcome != invocation["outcome"] or report != receipt["provider_report"]
                    or reason is not None or invocation["reason"] is not None
                    or invocation["input_snapshots_unchanged"] is not True):
                raise ReviewError("captured provider report/outcome mismatch")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ReviewError("invalid capture structure or binding") from exc
    return {"schema": "chimera-capture-validation/v1", "status": "CONFIRMED",
            "scope": "RECORDED_BYTES_MATCH_EXTERNALLY_PINNED_RECEIPT_ONLY",
            "receipt_digest": expected_receipt, "provider_outcome": receipt["invocation"]["outcome"],
            "provider_execution_reproduced": "NOT_RUN", "independent_observation": "UNKNOWN",
            "general_claim_verdict": "NOT_ASSESSED"}
