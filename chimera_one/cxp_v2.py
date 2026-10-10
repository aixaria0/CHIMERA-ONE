from __future__ import annotations

from typing import Any
import hashlib
import json

SCHEMA = "chimera-run/v2"
DOMAIN = "run/v2"
PREFIX = b"CHIMERA-CXP\0"
ALLOWED_STEP_STATES = {"PLANNED", "AUTHORIZED", "EXECUTING", "OBSERVED", "ATTESTED", "REPLAYED", "VERIFIED", "CERTIFIED", "BLOCKED", "FAILED", "CONTRADICTED", "UNKNOWN"}
CERTIFICATE_LEVELS = {"EXECUTION", "ASSURED", "FINALIZED"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest_run(value: dict[str, Any]) -> str:
    body = dict(value)
    body.pop("cxp_sha256", None)
    h = hashlib.sha256()
    h.update(PREFIX)
    h.update(DOMAIN.encode("ascii"))
    h.update(b"\0")
    h.update(canonical_bytes(body))
    return h.hexdigest()


def validate_run_v2(run: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    if run.get("schema") != SCHEMA:
        errors.append("schema")
    if run.get("cxp_version") != 1:
        errors.append("cxp_version")
    if not isinstance(run.get("run_id"), str) or not run.get("run_id"):
        errors.append("run_id")
    if not isinstance(run.get("objective"), str) or not run.get("objective"):
        errors.append("objective")
    if run.get("cxp_sha256") != digest_run(run):
        errors.append("cxp_digest")

    policy = run.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy")
    else:
        if policy.get("unrestricted_execution") is not False:
            errors.append("unrestricted_execution")
        if policy.get("claim_promotion_requires_evidence") is not True:
            errors.append("claim_promotion_policy")

    steps = run.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps")
    else:
        seen: set[str] = set()
        for step in steps:
            if not isinstance(step, dict):
                errors.append("step_shape")
                continue
            sid = step.get("id")
            if not isinstance(sid, str) or not sid or sid in seen:
                errors.append("step_id")
            else:
                seen.add(sid)
            if step.get("state") not in ALLOWED_STEP_STATES:
                errors.append("step_state")
            dependencies = step.get("depends_on", [])
            if not isinstance(dependencies, list) or any(dep not in seen for dep in dependencies):
                errors.append("step_dependency_order")

    claims = run.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("claims")
    else:
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("status") != "HYPOTHESIS":
                errors.append("claim_promotion")

    authority = run.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority")
    else:
        if authority.get("external_truth") != "UNKNOWN":
            errors.append("external_truth_must_remain_unknown")
        if authority.get("qpu_execution") not in {"UNKNOWN", "CONFIRMED"}:
            errors.append("qpu_execution_state")
        if authority.get("hardware_attestation") not in {"UNKNOWN", "CONFIRMED"}:
            errors.append("hardware_attestation_state")

    certificate = run.get("certificate")
    level = certificate.get("status") if isinstance(certificate, dict) else None
    if level not in CERTIFICATE_LEVELS:
        errors.append("certificate_level")
    elif level == "ASSURED":
        if not isinstance(authority, dict) or authority.get("two_process_quorum") != "CONFIRMED":
            errors.append("assured_without_quorum")
    elif level == "FINALIZED":
        consensus = run.get("consensus")
        if not isinstance(consensus, dict) or consensus.get("status") != "CONFIRMED" or consensus.get("finality") != "CONFIRMED":
            errors.append("finalized_without_consensus")

    execution = run.get("execution")
    if not isinstance(execution, dict) or not execution.get("receipt_sha256"):
        errors.append("execution_receipt")
    evidence = run.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("provider_certificate_sha256"):
        errors.append("provider_certificate")

    return {
        "schema": "chimera-cxp-validation/v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "cxp_sha256": run.get("cxp_sha256"),
    }


def load_run(path: str) -> dict[str, Any]:
    value = json.loads(open(path, "r", encoding="utf-8").read())
    if not isinstance(value, dict):
        raise ValueError("CXP run must be a JSON object")
    return value
