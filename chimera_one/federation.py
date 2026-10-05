from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catalog import Capability


class FederationError(ValueError):
    pass


def _repo_name_from_url(url: str) -> str:
    marker = "github.com/"
    if marker not in url:
        raise FederationError(f"unsupported repository URL: {url}")
    return url.split(marker, 1)[1].removesuffix(".git").strip("/")


def validate_provider(data: dict[str, Any]) -> None:
    required = {"schema", "repository", "role", "control_plane", "version", "entrypoints", "boundaries"}
    missing = required - data.keys()
    if missing:
        raise FederationError("provider missing fields: " + ", ".join(sorted(missing)))
    if data["schema"] != "chimera-provider/v1":
        raise FederationError("unsupported provider schema")
    if not isinstance(data["entrypoints"], list) or not data["entrypoints"]:
        raise FederationError("provider requires entrypoints")
    if not isinstance(data["boundaries"], list) or not data["boundaries"]:
        raise FederationError("provider requires boundaries")
    seen: set[str] = set()
    for entry in data["entrypoints"]:
        for field in ("capability", "mode", "network", "mutation"):
            if field not in entry:
                raise FederationError(f"entrypoint missing {field}")
        cap = entry["capability"]
        if not isinstance(cap, str) or not cap:
            raise FederationError("entrypoint capability must be non-empty")
        if cap in seen:
            raise FederationError(f"duplicate entrypoint capability: {cap}")
        seen.add(cap)

        has_command = "command" in entry
        has_service = "transport" in entry or "endpoint" in entry
        if has_command == has_service:
            raise FederationError(
                f"entrypoint {cap} requires exactly one invocation form: command or transport+endpoint"
            )
        if has_command:
            command = entry["command"]
            if not isinstance(command, list) or not command or any(not isinstance(v, str) or not v for v in command):
                raise FederationError(f"invalid command for {cap}")
        else:
            if "transport" not in entry or "endpoint" not in entry:
                raise FederationError(f"service entrypoint {cap} requires transport and endpoint")
            if not isinstance(entry["transport"], str) or not entry["transport"]:
                raise FederationError(f"invalid transport for {cap}")
            endpoint = entry["endpoint"]
            if not isinstance(endpoint, dict) or not endpoint:
                raise FederationError(f"invalid endpoint for {cap}")
            protocol = endpoint.get("protocol")
            if not isinstance(protocol, str) or not protocol:
                raise FederationError(f"service endpoint {cap} requires protocol")


def federation_report(
    workspace: Path,
    constellation: dict[str, Any],
    capabilities: list[Capability],
) -> dict[str, Any]:
    known = {cap.id: cap for cap in capabilities}
    reports: list[dict[str, Any]] = []
    for repo in constellation["repositories"]:
        checkout = str(repo.get("provider_checkout") or repo.get("checkout") or repo["name"])
        manifest_path = workspace / checkout / "chimera.provider.json"
        issues: list[str] = []
        manifest: dict[str, Any] | None = None
        if not manifest_path.exists():
            issues.append("provider manifest missing")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                validate_provider(manifest)
            except (OSError, json.JSONDecodeError, FederationError) as exc:
                issues.append(str(exc))

        declared: list[str] = []
        if manifest is not None and not issues:
            expected_repo = _repo_name_from_url(str(repo["url"]))
            if manifest["repository"] != expected_repo:
                issues.append(f"repository mismatch: {manifest['repository']} != {expected_repo}")
            if manifest["role"] != repo["role"]:
                issues.append(f"role mismatch: {manifest['role']} != {repo['role']}")
            if manifest["control_plane"] != "aixaria0/CHIMERA-ONE":
                issues.append("control_plane does not point to aixaria0/CHIMERA-ONE")
            declared = [entry["capability"] for entry in manifest["entrypoints"]]
            unknown = [cap for cap in declared if cap not in known]
            if unknown:
                issues.append("capabilities missing from central catalog: " + ", ".join(unknown))
            wrong_provider = [cap for cap in declared if cap in known and known[cap].provider != repo["name"]]
            if wrong_provider:
                issues.append("capabilities assigned to another provider: " + ", ".join(wrong_provider))
        reports.append({
            "repository": repo["name"],
            "checkout": checkout,
            "manifest": str(manifest_path),
            "declared_capabilities": declared,
            "valid": not issues,
            "issues": issues,
        })
    return {
        "schema": "chimera-federation-report/v1",
        "valid": all(item["valid"] for item in reports),
        "providers": reports,
    }
