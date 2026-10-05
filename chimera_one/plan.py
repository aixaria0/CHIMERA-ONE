from __future__ import annotations

import hashlib
from typing import Any

from .catalog import Capability


class PlanError(ValueError):
    pass


def _run_id(objective: str, domain: str) -> str:
    raw = f"chimera-run/v1\0{domain}\0{objective}".encode("utf-8")
    return "run-" + hashlib.sha256(raw).hexdigest()[:20]


def build_plan(objective: str, domain: str, capabilities: list[Capability]) -> dict[str, Any]:
    objective = objective.strip()
    if not objective:
        raise PlanError("objective must not be empty")
    by_id = {c.id: c for c in capabilities}
    required = [
        "ritualgraph.compile",
        "chimera.route",
        "aether.execute-allowlisted",
        "assurance.run",
        "omega.verify",
        "ritualgraph.evaluate-invariants",
        "chimera.council",
    ]
    if domain == "rchain-audit":
        required.insert(3, "rchain-audit.first-divergence")
    elif domain != "general":
        raise PlanError(f"unsupported domain: {domain}")
    missing = [cid for cid in required if cid not in by_id]
    if missing:
        raise PlanError("missing capabilities: " + ", ".join(missing))

    steps = []
    dependencies: list[str] = []
    for index, capability_id in enumerate(required, start=1):
        cap = by_id[capability_id]
        step_id = f"s{index:02d}"
        step = {
            "id": step_id,
            "capability": capability_id,
            "provider": cap.provider,
            "kind": cap.raw["kind"],
            "depends_on": list(dependencies[-2:]),
            "trust": cap.raw["trust"],
            "state": "PLANNED",
        }
        steps.append(step)
        dependencies.append(step_id)

    return {
        "schema": "chimera-run/v1",
        "run_id": _run_id(objective, domain),
        "objective": objective,
        "domain": domain,
        "policy": {
            "automatic_mutation": False,
            "automatic_deployment": False,
            "unrestricted_execution": False,
            "claim_promotion_requires_evidence": True,
        },
        "steps": steps,
        "claims": [{
            "id": "claim-objective",
            "statement": objective,
            "status": "HYPOTHESIS",
            "evidence": [],
        }],
    }
