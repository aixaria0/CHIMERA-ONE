from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DOMAIN = b"chimera-protocol/v1\0"
_STATUSES = {
    "HYPOTHESIS", "PLAUSIBLE", "OBSERVED", "REPRODUCED", "CORROBORATED",
    "VERIFIED_WITHIN_SCOPE", "CONTRADICTED", "INCONCLUSIVE", "UNKNOWN",
}


def _reject_float(value: Any) -> None:
    if isinstance(value, float):
        raise ValueError("floating-point numbers are not canonical protocol values")
    if isinstance(value, list):
        for item in value:
            _reject_float(item)
    elif isinstance(value, dict):
        for item in value.values():
            _reject_float(item)


def canonical_json(value: Any) -> bytes:
    _reject_float(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def protocol_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(DOMAIN + canonical_json(value)).hexdigest()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_run(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    digest: str | None = None
    try:
        digest = protocol_digest(value)
    except ValueError as exc:
        errors.append(str(exc))
    if not isinstance(value, dict):
        errors.append("run must be a JSON object")
        return {"schema": "chimera-validation-report/v1", "valid": False, "digest": digest, "errors": errors}
    if value.get("schema") != "chimera-run/v1":
        errors.append("schema must equal chimera-run/v1")
    for key in ("run_id", "objective"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            errors.append(f"{key} must be a non-empty string")
    if value.get("domain") not in {"general", "rchain-audit"}:
        errors.append("domain must be general or rchain-audit")
    policy = value.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        for key in ("automatic_mutation", "automatic_deployment", "unrestricted_execution"):
            if policy.get(key) is not False:
                errors.append(f"policy.{key} must be false")
        if policy.get("claim_promotion_requires_evidence") is not True:
            errors.append("policy.claim_promotion_requires_evidence must be true")
    steps = value.get("steps")
    graph: dict[str, list[str]] = {}
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty array")
    else:
        ids: set[str] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"steps[{index}] must be an object")
                continue
            step_id = step.get("id")
            if not isinstance(step_id, str) or not step_id:
                errors.append("id must be a non-empty string")
                continue
            if step_id in ids:
                errors.append(f"duplicate step id: {step_id}")
            ids.add(step_id)
            deps = step.get("depends_on")
            if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
                errors.append(f"depends_on must be an array for step {step_id}")
                deps = []
            graph[step_id] = list(deps)
        for step_id, deps in graph.items():
            for dep in deps:
                if dep not in ids:
                    errors.append(f"step {step_id} depends on unknown step {dep}")
                if dep == step_id:
                    errors.append(f"step {step_id} depends on itself")
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(node: str) -> bool:
            if node in visited:
                return False
            if node in visiting:
                return True
            visiting.add(node)
            if any(dep in graph and visit(dep) for dep in graph.get(node, [])):
                return True
            visiting.remove(node)
            visited.add(node)
            return False
        if any(visit(node) for node in graph):
            errors.append("step dependency graph contains a cycle")
    claims = value.get("claims")
    if not isinstance(claims, list):
        errors.append("claims must be an array")
    else:
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                errors.append(f"claims[{index}] must be an object")
                continue
            if claim.get("status") not in _STATUSES:
                errors.append(f"claims[{index}] has invalid status")
            if not isinstance(claim.get("evidence"), list):
                errors.append(f"claims[{index}].evidence must be an array")
    return {"schema": "chimera-validation-report/v1", "valid": not errors, "digest": digest, "errors": errors}
