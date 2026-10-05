from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KINDS = {"reason", "plan", "simulate", "execute", "observe", "verify", "attest", "audit"}
AUTHORITIES = {"advisory", "bounded", "verification"}
NETWORKS = {"none", "loopback", "explicit"}
MUTATIONS = {"none", "workspace", "external-explicit"}
EVIDENCE = {"none", "digest", "receipt", "reproducible"}


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Capability:
    raw: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.raw["id"])

    @property
    def provider(self) -> str:
        return str(self.raw["provider"])


def _require_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{field} must be a non-empty string")


def validate_capability(item: dict[str, Any]) -> None:
    required = {"schema", "id", "provider", "version", "kind", "inputs", "outputs", "trust"}
    missing = sorted(required - item.keys())
    if missing:
        raise CatalogError(f"missing capability fields: {', '.join(missing)}")
    if item["schema"] != "chimera-capability/v1":
        raise CatalogError("unsupported capability schema")
    for field in ("id", "provider", "version"):
        _require_text(item[field], field)
    if item["kind"] not in KINDS:
        raise CatalogError(f"unsupported capability kind: {item['kind']}")
    for field in ("inputs", "outputs"):
        value = item[field]
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise CatalogError(f"{field} must be a list of strings")
        if len(value) != len(set(value)):
            raise CatalogError(f"{field} must contain unique values")
    trust = item["trust"]
    if not isinstance(trust, dict):
        raise CatalogError("trust must be an object")
    if trust.get("authority") not in AUTHORITIES:
        raise CatalogError("invalid trust.authority")
    if trust.get("network") not in NETWORKS:
        raise CatalogError("invalid trust.network")
    if trust.get("mutation") not in MUTATIONS:
        raise CatalogError("invalid trust.mutation")
    if trust.get("evidence") not in EVIDENCE:
        raise CatalogError("invalid trust.evidence")


def load_catalog(path: Path) -> list[Capability]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "chimera-capability-catalog/v1":
        raise CatalogError("unsupported catalog schema")
    raw = data.get("capabilities")
    if not isinstance(raw, list):
        raise CatalogError("capabilities must be a list")
    seen: set[str] = set()
    result: list[Capability] = []
    for item in raw:
        if not isinstance(item, dict):
            raise CatalogError("each capability must be an object")
        validate_capability(item)
        cap = Capability(item)
        if cap.id in seen:
            raise CatalogError(f"duplicate capability id: {cap.id}")
        seen.add(cap.id)
        result.append(cap)
    return result
