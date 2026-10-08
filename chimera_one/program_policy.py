"""Derive one narrow routing choice from externally pinned saved AG evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .protocol import canonical_json

EVIDENCE_SCHEMA = "one-program-routing-evidence/v1"
POLICY_SCHEMA = "one-program-routing-policy/v1"
SCOPE = "EXACT_V3_SAVED_NATIVE_PROGRAM_EVIDENCE_ONLY"
KINDS = ["integer-expression", "state-transition", "directed-reachability"]
AUTHORITY = {
    "answer_origin": "FIXED_LOCAL_ALGORITHM",
    "routing_basis": "TWO_SAVED_MATCHED_REQUEST_SUITES",
    "model_execution": "ATTRIBUTED_NOT_ATTESTED",
    "training_data_independence": "NOT_ESTABLISHED",
    "tool_cpu_budget": "NOT_MEASURED",
    "generalization_outside_selected_families": "NOT_ESTABLISHED",
    "collective_superiority": "NOT_ESTABLISHED",
    "general_intelligence": "NOT_ASSESSED",
    "automatic_promotion": "NOT_PERFORMED",
}
REVIEWED_NATIVE_PINS = {
    "artifact_zip": "sha256:d0cbd4821fb4ccfc2b98ed62db0604421d6aad648d7b58f5bcc1cd5b2550c1c9",
    "model_manifest": "sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b",
    "regression_suite": "sha256:887018db0efb7f2d44fcea9ed03b2773c089b54d683d8e4367c154eb55ce86a8",
    "regression_report": "sha256:77351b7ae781d7934f2b24700e5c66f553630ce490649c3d62fad3a0647607db",
    "transfer_suite": "sha256:41a58fb0db1d03f26cdf62b912414f761fce4dd9f113ea6c0b672df608a18a17",
    "transfer_report": "sha256:2c202b27a824093b37cfd41de212597f8869e1b11446291b8f3d92113a9f0054",
}
NATIVE_FILES = {
    "regression": {
        "suite": ("regression-suite.json", "sha256:1f7c4d455e5793d16e46733ef5efc393c57409f42e01ea96e77b86a3d664b5f4"),
        "report": ("regression-report.json", "sha256:6ed7da875c483fed037ea74fc1529153f2d486e843ea28c2e68c2cef472422ca"),
    },
    "transfer": {
        "suite": ("transfer-suite.json", "sha256:9001df0043ad9909fab3302d175db37e52dc612e534a3896d8bffd40b49d1020"),
        "report": ("transfer-report.json", "sha256:338e8758b21be0c183b7e10072af0f1c34a3d276b17512d97d88d9ab63a8ee54"),
    },
}


class ProgramPolicyError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProgramPolicyError(message)


def fields(value: Any, expected: tuple[str, ...]) -> None:
    require(isinstance(value, dict) and set(value) == set(expected), "unsupported program-policy fields")


def pin(value: Any) -> str:
    require(isinstance(value, str) and len(value) == 71 and value.startswith("sha256:"), "SHA-256 pin required")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise ProgramPolicyError("SHA-256 pin required") from exc
    return value


def digest(domain: str, value: Any) -> str:
    return "sha256:" + hashlib.sha256(b"CHIMERA-ONE\0" + domain.encode() + b"\0" + canonical_json(value)).hexdigest()


def evidence_digest(value: dict[str, Any]) -> str:
    return digest("program-routing-evidence/v1", {k: v for k, v in value.items() if k != "evidence_digest"})


def policy_digest(value: dict[str, Any]) -> str:
    return digest("program-routing-policy/v1", {k: v for k, v in value.items() if k != "policy_digest"})


def load_json(path: Path, limit: int = 65536) -> dict[str, Any]:
    raw = path.read_bytes()
    require(0 < len(raw) <= limit, "bounded JSON evidence required")
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            require(key not in result and key.isascii() and len(key) <= 128, "duplicate or unsupported JSON key")
            result[key] = item
        return result
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False, "nonfinite JSON value"))
    require(isinstance(value, dict), "JSON object required")
    return value


def _file_json(path: Path, expected_bytes: str, limit: int) -> dict[str, Any]:
    raw = path.read_bytes()
    require("sha256:" + hashlib.sha256(raw).hexdigest() == expected_bytes, "native fixture byte pin mismatch")
    return load_json(path, limit)


def _native_digest(domain: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(b"CHIMERA-AG\0" + domain.encode() + b"\0" + payload).hexdigest()


def validate_native_fixture(native_dir: Path, evidence: dict[str, Any]) -> None:
    """Verify retained native suite/report bytes and bind their summaries to compact evidence."""
    for selected, suite_evidence in zip(("regression", "transfer"), evidence["suites"], strict=True):
        names = NATIVE_FILES[selected]
        suite = _file_json(native_dir / names["suite"][0], names["suite"][1], 16384)
        report = _file_json(native_dir / names["report"][0], names["report"][1], 1024 * 1024)
        suite_pin = _native_digest("reference-suite/v1", suite)
        report_pin = _native_digest("program-benchmark/v3", {k: v for k, v in report.items() if k != "report_digest"})
        require(suite_pin == suite_evidence["suite_digest"], "retained native suite pin mismatch")
        require(report.get("report_digest") == report_pin == suite_evidence["report_digest"],
                "retained native report pin mismatch")
        selection = report.get("selection")
        require(isinstance(selection, dict) and selection.get("suite_digest") == suite_pin and
                selection.get("model_manifest_digest") == evidence["model_manifest_digest"] and
                selection.get("repeats") == 2, "retained native report selection mismatch")
        summary = report.get("summary")
        require(isinstance(summary, dict) and summary.get("status") == "COMPLETED" and
                summary.get("pairs") == suite_evidence["pairs"] and
                summary.get("complete_pairs") == suite_evidence["complete_pairs"],
                "retained native report coverage mismatch")
        for arm in ("single", "council"):
            for metric in ("verified_answers", "false_accepts", "requests", "input_tokens",
                           "generated_tokens", "elapsed_ms"):
                require(summary.get(f"{arm}_{metric}") == suite_evidence[arm][metric],
                        "compact metrics changed from retained native report")


def _count(value: Any, upper: int) -> int:
    require(type(value) is int and 0 <= value <= upper, "invalid nonnegative metric")
    return value


def validate_evidence(value: dict[str, Any], expected_evidence: str, native_dir: Path) -> dict[str, Any]:
    fields(value, ("schema", "scope", "provider", "artifact", "model_manifest_digest", "task_kinds",
                   "suites", "authority", "evidence_digest"))
    require(value["schema"] == EVIDENCE_SCHEMA and value["scope"] == SCOPE, "program evidence schema/scope mismatch")
    fields(value["provider"], ("repository", "revision", "tree"))
    require(value["provider"] == {"repository": "aixaria0/Chimera-AG",
            "revision": "efe372e1065f0cfdb8f3cafee0264632d54dc98f",
            "tree": "ddfd4b1e09d0ba002f4f50292ffe87cf28d4cfb6"}, "unsupported provider selection")
    fields(value["artifact"], ("workflow_run", "artifact_id", "size_bytes", "zip_sha256"))
    require(value["artifact"]["workflow_run"] == 37821064387 and value["artifact"]["artifact_id"] == 11570730020 and
            value["artifact"]["size_bytes"] == 57658, "unsupported acquisition occurrence")
    require(value["artifact"]["zip_sha256"] == REVIEWED_NATIVE_PINS["artifact_zip"] and
            value["model_manifest_digest"] == REVIEWED_NATIVE_PINS["model_manifest"],
            "reviewed artifact/model pin changed")
    require(value["task_kinds"] == KINDS and value["authority"] == AUTHORITY, "program evidence authority/families changed")
    suites = value["suites"]
    require(isinstance(suites, list) and all(isinstance(item, dict) for item in suites) and
            [item.get("name") for item in suites] == ["regression", "transfer"],
            "exact regression and transfer suites required")
    for selected, suite in zip(("regression", "transfer"), suites, strict=True):
        fields(suite, ("name", "suite_digest", "report_digest", "pairs", "complete_pairs", "single", "council"))
        require(suite["suite_digest"] == REVIEWED_NATIVE_PINS[f"{selected}_suite"] and
                suite["report_digest"] == REVIEWED_NATIVE_PINS[f"{selected}_report"],
                "reviewed suite/report pin changed")
        require(_count(suite["pairs"], 24) == _count(suite["complete_pairs"], 24) == 12, "incomplete program evidence")
        for arm in ("single", "council"):
            metrics = suite[arm]
            fields(metrics, ("verified_answers", "false_accepts", "requests", "input_tokens", "generated_tokens", "elapsed_ms"))
            _count(metrics["verified_answers"], 12); _count(metrics["false_accepts"], 12)
            require(_count(metrics["requests"], 96) == 48, "matched request count changed")
            _count(metrics["input_tokens"], 1000000); _count(metrics["generated_tokens"], 1000000)
            _count(metrics["elapsed_ms"], 900000)
    pin(expected_evidence)
    require(value["evidence_digest"] == expected_evidence == evidence_digest(value), "external program evidence pin mismatch")
    validate_native_fixture(native_dir, value)
    return value


def select_program_policy(value: dict[str, Any], *, expected_evidence: str, native_dir: Path) -> dict[str, Any]:
    evidence = validate_evidence(value, expected_evidence, native_dir)
    single_verified = sum(s["single"]["verified_answers"] for s in evidence["suites"])
    council_verified = sum(s["council"]["verified_answers"] for s in evidence["suites"])
    single_elapsed = sum(s["single"]["elapsed_ms"] for s in evidence["suites"])
    council_elapsed = sum(s["council"]["elapsed_ms"] for s in evidence["suites"])
    eligible = all(s["single"]["false_accepts"] == s["council"]["false_accepts"] == 0 and
                   s["single"]["verified_answers"] >= s["council"]["verified_answers"] and
                   s["single"]["elapsed_ms"] < s["council"]["elapsed_ms"] for s in evidence["suites"])
    result = {
        "schema": POLICY_SCHEMA, "scope": SCOPE, "evidence_digest": expected_evidence,
        "decision": "SINGLE_FOUR_SAMPLE_CHECKED_PROGRAMS" if eligible else "NO_SELECTION",
        "rationale": "NONINFERIOR_VERIFIED_ANSWERS_AND_LOWER_OBSERVED_ELAPSED_TIME_ON_BOTH_SUITES" if eligible else
                     "SAVED_EVIDENCE_DOES_NOT_AUTHORIZE_A_ROUTE",
        "task_kinds": list(KINDS),
        "aggregate": {"single_verified_answers": single_verified, "council_verified_answers": council_verified,
                      "single_elapsed_ms": single_elapsed, "council_elapsed_ms": council_elapsed,
                      "single_requests": sum(s["single"]["requests"] for s in evidence["suites"]),
                      "council_requests": sum(s["council"]["requests"] for s in evidence["suites"])},
        "authority": dict(AUTHORITY), "policy_digest": "",
    }
    result["policy_digest"] = policy_digest(result)
    return result


def validate_program_policy(policy: dict[str, Any], evidence: dict[str, Any], *, expected_evidence: str,
                            expected_policy: str, native_dir: Path) -> dict[str, Any]:
    derived = select_program_policy(evidence, expected_evidence=expected_evidence, native_dir=native_dir)
    pin(expected_policy)
    require(policy == derived and policy.get("policy_digest") == expected_policy,
            "program policy bytes, evidence or decision changed")
    return {"status": "CONFIRMED", "scope": SCOPE, "evidence_digest": expected_evidence,
            "policy_digest": expected_policy, "decision": derived["decision"],
            "fresh_inference": "NOT_RUN", "authority": dict(AUTHORITY)}
