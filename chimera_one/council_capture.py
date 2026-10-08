"""One pinned, bounded local-model experiment; saved checks never run inference."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
import uuid

from .offline_review import ReviewError, _bounded_read, _git, _hex, _invoke, _json, sha256
from .protocol import canonical_json

REPOSITORY = "aixaria0/Chimera-AG"
REVISION = "6c529e802833903db75b6f8358031082a8373b2b"
TREE = "173afbde5f5d058fe2fad59da856617ab977d05f"
MANIFEST_SHA256 = "c32a032ee6fbbb5dd09dc63d96ce7a9ad6a51161f5e5bc043165e8911062dfb9"
SOURCE_FILES = {
    "chimera/__init__.py": "39a90c4c7b53ff663984066199b5afc62a2af277fa385cf176454e3163c3ed67",
    "chimera/budget_benchmark.py": "14271c41e3ded8881a6c8b17f3b3fa538421effa353c64228ee11b940091fdb0",
    "chimera/council.py": "53c2e4b1b8f9532a4291eac8b6b079633a71d669687ed1486b2d4d932c06a7e3",
    "chimera/fabric.py": "c59cfa1e911473658fd30a9beaad09302f90f304179aead2e6653b4c2df6e636",
}
SCHEMA = "chimera-council-capture/v1"
SCOPE = "ONE_PINNED_LOCAL_CHIMERA_BUDGET_EXPERIMENT_ONLY"
REPORT_SCOPE = "SAVED_LOCAL_MODEL_TRANSCRIPTS_AND_FIXED_REFERENCE_TASKS_ONLY"
AUTHORITY = {"model_agreement": "ADVISORY_ONLY", "inference_execution": "ATTRIBUTED_NOT_ATTESTED",
             "model_identity": "OLLAMA_REPORTED_MANIFEST_ONLY", "role_independence": "NOT_ESTABLISHED",
             "equal_cpu_budget": "NOT_ESTABLISHED", "training_data_independence": "NOT_ESTABLISHED",
             "general_intelligence": "NOT_ASSESSED", "automatic_promotion": "NOT_PERFORMED",
             "os_network_sandbox": "NOT_ESTABLISHED", "host_runtime_closure": "UNKNOWN"}
REPORT_AUTHORITY = {k: v for k, v in AUTHORITY.items()
                    if k not in ("model_agreement", "os_network_sandbox", "host_runtime_closure")}
FILE_LIMITS = {"inputs/suite.json": 16384, "provider.stdout": 131072, "provider.stderr": 131072,
               "benchmark.json": 1048576, "checker.stdout": 131072, "checker.stderr": 131072}
BOOTSTRAP = ("import sys,runpy;root=sys.argv.pop(1);sys.path.insert(0,root);"
             "sys.argv[0]='chimera-budget-benchmark';"
             "runpy.run_module('chimera.budget_benchmark',run_name='__main__')")


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def fields(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), "unsupported object fields")


def pin(value):
    require(isinstance(value, str) and value.startswith("sha256:") and _hex(value[7:]), "explicit SHA-256 pin required")


def ag_digest(domain, value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    return "sha256:" + sha256(b"CHIMERA-AG\0" + domain.encode() + b"\0" + encoded)


def receipt_digest(value):
    body = {k: v for k, v in value.items() if k != "receipt_digest"}
    return "sha256:" + sha256(b"CHIMERA-ONE\0council/capture/v1\0" + canonical_json(body))


def provider_ref():
    return {"repository": REPOSITORY, "revision": REVISION, "tree": TREE,
            "manifest_sha256": MANIFEST_SHA256, "source_files_sha256": dict(SOURCE_FILES)}


def snapshot_provider(checkout, target):
    checkout = checkout.resolve(strict=True)
    origin = _git(checkout, "remote", "get-url", "origin")
    if origin.startswith("git@github.com:"):
        origin = "https://github.com/" + origin[len("git@github.com:"):]
    require(_git(checkout, "rev-parse", "HEAD") == REVISION and
            _git(checkout, "rev-parse", "HEAD^{tree}") == TREE and
            origin.removesuffix(".git").rstrip("/") == "https://github.com/" + REPOSITORY and
            not _git(checkout, "status", "--porcelain"), "provider revision/tree/origin/cleanliness mismatch")
    manifest = _bounded_read(checkout / "chimera.provider.json", 16384)
    require(sha256(manifest) == MANIFEST_SHA256, "provider manifest changed")
    descriptor = _json(manifest)
    require(isinstance(descriptor, dict) and descriptor.get("repository") == REPOSITORY and
            descriptor.get("control_plane") == "aixaria0/CHIMERA-ONE" and
            descriptor.get("version") == "0.13.0", "provider identity changed")
    for name, expected in SOURCE_FILES.items():
        raw = _bounded_read(checkout / name, 65536)
        require(sha256(raw) == expected, "selected provider source bytes changed")
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return provider_ref()


def selections(model, expected_model, expected_suite, repeats, host):
    pin(expected_model)
    pin(expected_suite)
    require(isinstance(model, str) and re.fullmatch(r"[a-z0-9][a-z0-9._:/-]{0,95}", model) and
            not model.endswith("-cloud"), "unsupported local model")
    require(type(repeats) is int and 1 <= repeats <= 3, "unsupported repeat count")
    parsed = urlsplit(host)
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.username is None and
            parsed.password is None and parsed.path in ("", "/") and not parsed.query and not parsed.fragment and
            parsed.port is not None and 1024 <= parsed.port <= 65535, "explicit loopback model host required")
    return {"model": model, "model_manifest_digest": expected_model, "suite_digest": expected_suite,
            "repeats": repeats, "host": f"http://127.0.0.1:{parsed.port}"}


def report_selection(raw, suite, selected, expected_report):
    pin(expected_report)
    report = _json(raw)
    fields(report, ("schema", "scope", "occurrence", "selection", "budget", "runtime", "results", "summary", "authority", "report_digest"))
    require(report["schema"] == "chimera-budget-benchmark/v2" and report["scope"] == REPORT_SCOPE and
            canonical_json(report["authority"]) == canonical_json(REPORT_AUTHORITY), "provider report changed authority")
    require(report["report_digest"] == expected_report == ag_digest("budget-benchmark/v2", {k: v for k, v in report.items() if k != "report_digest"}),
            "selected report digest mismatch")
    require(canonical_json(report["selection"]) == canonical_json({k: v for k, v in selected.items() if k != "host"}), "report selection changed")
    require(ag_digest("reference-suite/v1", suite) == selected["suite_digest"], "selected suite mismatch")
    return report


def checker_command(snapshot, suite, report, selected, expected_report):
    return [sys.executable, "-I", "-B", "-c", BOOTSTRAP, str(snapshot), "validate",
            "--suite", str(suite), "--report", str(report), "--expect-report", expected_report,
            "--expect-suite", selected["suite_digest"], "--expect-model", selected["model_manifest_digest"]]


def checked_result(stdout, stderr, exit_code, reason, selected, report):
    require(type(exit_code) is int and exit_code == 0 and reason is None and stderr == b"", "saved checker did not succeed cleanly")
    value = _json(stdout)
    fields(value, ("schema", "status", "scope", "report_digest", "suite_digest", "model_manifest_digest", "summary", "raw_inference_reproduced", "authority"))
    expected = {"schema": "chimera-budget-benchmark-validation/v2", "status": "CONFIRMED", "scope": REPORT_SCOPE,
                "report_digest": report["report_digest"], "suite_digest": selected["suite_digest"],
                "model_manifest_digest": selected["model_manifest_digest"], "summary": report["summary"],
                "raw_inference_reproduced": "NOT_RUN", "authority": REPORT_AUTHORITY}
    require(canonical_json(value) == canonical_json(expected), "saved checker report changed scope or selected result")
    require(value["summary"].get("collective_superiority") == "NOT_ESTABLISHED", "unexpected superiority promotion")
    return value


def measure_council(*, checkout, suite, expected_suite, model, expected_model, repeats, host, output):
    selected = selections(model, expected_model, expected_suite, repeats, host)
    suite_raw = _bounded_read(suite, 16384)
    suite_value = _json(suite_raw)
    require(ag_digest("reference-suite/v1", suite_value) == expected_suite, "suite pin mismatch")
    output = output.absolute()
    require(not output.exists() and not output.is_symlink(), "capture output exists")
    output = output.resolve()
    provider = checkout.resolve(strict=True)
    require(output != provider and provider not in output.parents and output not in provider.parents and
            output != suite.resolve() and output not in suite.resolve().parents, "protected capture output")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="one-owned-council-", dir=output.parent) as temporary:
        root = Path(temporary)
        snapshot = root / "provider"
        ref = snapshot_provider(checkout, snapshot)
        inputs = root / "suite.json"
        inputs.write_bytes(suite_raw)
        produced = root / "benchmark.json"
        command = [sys.executable, "-I", "-B", "-c", BOOTSTRAP, str(snapshot), "measure",
                   "--suite", str(inputs), "--model", model, "--expect-model", expected_model,
                   "--host", selected["host"], "--repeats", str(repeats), "--output", str(produced), "--execute"]
        exit_code, stdout, stderr, reason = _invoke(command, root, timeout_seconds=900)
        saved = {"inputs/suite.json": suite_raw, "provider.stdout": stdout, "provider.stderr": stderr,
                 "benchmark.json": b"", "checker.stdout": b"", "checker.stderr": b""}
        outcome, report_pin, checker_exit = "BLOCKED", None, None
        explanation = reason or "provider report unavailable or unsupported"
        try:
            saved["benchmark.json"] = _bounded_read(produced, FILE_LIMITS["benchmark.json"])
            report_value = _json(saved["benchmark.json"])
            report = report_selection(saved["benchmark.json"], suite_value, selected, report_value.get("report_digest"))
            cli = _json(stdout)
            fields(cli, ("schema", "status", "report_digest", "summary"))
            require(type(exit_code) is int and exit_code in (0, 3) and reason is None and stderr == b"" and
                    cli["schema"] == "chimera-budget-benchmark-cli/v2" and cli["report_digest"] == report["report_digest"] and
                    canonical_json(cli["summary"]) == canonical_json(report["summary"]) and
                    cli["status"] == report["summary"].get("status") == ("COMPLETED" if exit_code == 0 else "INCOMPLETE"),
                    "native report/process disagreement")
            checker_exit, checked_stdout, checked_stderr, checked_reason = _invoke(
                checker_command(snapshot, inputs, produced, selected, report["report_digest"]), root)
            saved["checker.stdout"], saved["checker.stderr"] = checked_stdout, checked_stderr
            checked_result(checked_stdout, checked_stderr, checker_exit, checked_reason, selected, report)
            outcome, report_pin, explanation = cli["status"], report["report_digest"], None
        except (ReviewError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            explanation = reason or str(exc)[:1000]
        receipt = {"schema": SCHEMA, "scope": SCOPE, "invocation_id": str(uuid.uuid4()), "provider": ref,
                   "selection": selected, "invocation": {"outcome": outcome, "exit_code": exit_code,
                   "reason": explanation, "checker_exit_code": checker_exit}, "report_digest": report_pin,
                   "artifacts": {name: {"sha256": sha256(raw), "size_bytes": len(raw)} for name, raw in saved.items()},
                   "authority": dict(AUTHORITY)}
        receipt["receipt_digest"] = receipt_digest(receipt)
        output.mkdir(mode=0o700)
        for name, raw in saved.items():
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as target:
                target.write(raw)
            os.chmod(path, 0o600)
        with (output / "receipt.json").open("xb") as target:
            target.write(json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n")
        os.chmod(output / "receipt.json", 0o600)
        return receipt


def capture_bytes(root, expected_receipt):
    pin(expected_receipt)
    require(root.is_dir() and not root.is_symlink(), "capture directory required")
    actual = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "capture symlink refused")
        mode = path.stat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "capture special file refused")
        name = path.relative_to(root).as_posix()
        require(not stat.S_ISDIR(mode) or name == "inputs", "unexpected capture directory")
        if stat.S_ISREG(mode):
            actual.add(name)
    require(actual == set(FILE_LIMITS) | {"receipt.json"}, "capture inventory differs")
    receipt = _json(_bounded_read(root / "receipt.json", 16384))
    fields(receipt, ("schema", "scope", "invocation_id", "provider", "selection", "invocation", "report_digest", "artifacts", "authority", "receipt_digest"))
    require(receipt["receipt_digest"] == expected_receipt == receipt_digest(receipt), "capture receipt pin mismatch")
    require(receipt["schema"] == SCHEMA and receipt["scope"] == SCOPE and
            canonical_json(receipt["provider"]) == canonical_json(provider_ref()) and
            canonical_json(receipt["authority"]) == canonical_json(AUTHORITY), "capture scope/source/authority changed")
    require(isinstance(receipt["invocation_id"], str) and str(uuid.UUID(receipt["invocation_id"])) == receipt["invocation_id"], "invalid invocation ID")
    fields(receipt["artifacts"], FILE_LIMITS)
    raw = {}
    for name, bound in FILE_LIMITS.items():
        raw[name] = _bounded_read(root / name, bound)
        require(canonical_json(receipt["artifacts"][name]) == canonical_json(
            {"sha256": sha256(raw[name]), "size_bytes": len(raw[name])}), "capture bytes changed")
    fields(receipt["invocation"], ("outcome", "exit_code", "reason", "checker_exit_code"))
    return receipt, raw


def validate_council_capture(*, root, checkout, expected_receipt, expected_report, expected_suite, expected_model):
    receipt, raw = capture_bytes(root, expected_receipt)
    selected = receipt["selection"]
    fields(selected, ("model", "model_manifest_digest", "suite_digest", "repeats", "host"))
    require(canonical_json(selected) == canonical_json(selections(selected["model"], expected_model, expected_suite,
                                                                  selected["repeats"], selected["host"])), "external selection mismatch")
    suite = _json(raw["inputs/suite.json"])
    require(ag_digest("reference-suite/v1", suite) == expected_suite, "saved suite pin mismatch")
    invoked = receipt["invocation"]
    for key in ("exit_code", "checker_exit_code"):
        require(invoked[key] is None or (type(invoked[key]) is int and -255 <= invoked[key] <= 255), "invalid process exit")
    require(invoked["outcome"] in ("COMPLETED", "INCOMPLETE", "BLOCKED"), "unsupported captured outcome")
    if invoked["outcome"] == "BLOCKED":
        require(expected_report == "NOT_RUN" and receipt["report_digest"] is None and
                isinstance(invoked["reason"], str) and 0 < len(invoked["reason"]) <= 1000, "explicit blocked-report selection required")
        return {"schema": "chimera-council-capture-validation/v1", "status": "CONFIRMED",
                "scope": "CAPTURE_BYTES_ONLY", "receipt_digest": expected_receipt,
                "captured_outcome": "BLOCKED", "saved_transcripts_recomputed": "NOT_RUN",
                "fresh_inference": "NOT_RUN", "authority": dict(AUTHORITY)}
    require(invoked["reason"] is None and invoked["checker_exit_code"] == 0 and
            invoked["exit_code"] == (0 if invoked["outcome"] == "COMPLETED" else 3), "captured process/outcome mismatch")
    require(receipt["report_digest"] == expected_report, "external report selection mismatch")
    report = report_selection(raw["benchmark.json"], suite, selected, expected_report)
    cli = _json(raw["provider.stdout"])
    fields(cli, ("schema", "status", "report_digest", "summary"))
    require(cli["schema"] == "chimera-budget-benchmark-cli/v2" and cli["status"] == invoked["outcome"] == report["summary"].get("status") and
            cli["report_digest"] == expected_report and canonical_json(cli["summary"]) == canonical_json(report["summary"]) and
            raw["provider.stderr"] == b"", "saved native report/process mismatch")
    checked_result(raw["checker.stdout"], raw["checker.stderr"], invoked["checker_exit_code"], None, selected, report)
    with tempfile.TemporaryDirectory(prefix="one-owned-council-recheck-") as temporary:
        private = Path(temporary)
        snapshot_provider(checkout, private / "provider")
        (private / "suite.json").write_bytes(raw["inputs/suite.json"])
        (private / "benchmark.json").write_bytes(raw["benchmark.json"])
        code, stdout, stderr, reason = _invoke(checker_command(private / "provider", private / "suite.json",
                                                             private / "benchmark.json", selected, expected_report), private)
        result = checked_result(stdout, stderr, code, reason, selected, report)
        require(stdout == raw["checker.stdout"] and stderr == raw["checker.stderr"], "saved checker transcript changed")
    return {"schema": "chimera-council-capture-validation/v1", "status": "CONFIRMED", "scope": REPORT_SCOPE,
            "receipt_digest": expected_receipt, "captured_outcome": invoked["outcome"],
            "saved_transcripts_recomputed": "CONFIRMED", "fresh_inference": "NOT_RUN",
            "report_digest": expected_report, "summary": result["summary"], "authority": dict(AUTHORITY)}
