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
    value = json.loads(raw)
    require(isinstance(value, dict), "JSON object required")
    return value


def _count(value: Any, upper: int) -> int:
    require(type(value) is int and 0 <= value <= upper, "invalid nonnegative metric")
    return value


def validate_evidence(value: dict[str, Any], expected_evidence: str) -> dict[str, Any]:
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
    pin(value["artifact"]["zip_sha256"]); pin(value["model_manifest_digest"])
    require(value["task_kinds"] == KINDS and value["authority"] == AUTHORITY, "program evidence authority/families changed")
    suites = value["suites"]
    require(isinstance(suites, list) and [item.get("name") for item in suites] == ["regression", "transfer"],
            "exact regression and transfer suites required")
    for suite in suites:
        fields(suite, ("name", "suite_digest", "report_digest", "pairs", "complete_pairs", "single", "council"))
        pin(suite["suite_digest"]); pin(suite["report_digest"])
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
    return value


def select_program_policy(value: dict[str, Any], *, expected_evidence: str) -> dict[str, Any]:
    evidence = validate_evidence(value, expected_evidence)
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
                            expected_policy: str) -> dict[str, Any]:
    derived = select_program_policy(evidence, expected_evidence=expected_evidence)
    pin(expected_policy)
    require(policy == derived and policy.get("policy_digest") == expected_policy,
            "program policy bytes, evidence or decision changed")
    return {"status": "CONFIRMED", "scope": SCOPE, "evidence_digest": expected_evidence,
            "policy_digest": expected_policy, "decision": derived["decision"],
            "fresh_inference": "NOT_RUN", "authority": dict(AUTHORITY)}
