from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def load_adapters(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "chimera-adapter-catalog/v1":
        raise ValueError("unsupported adapter catalog schema")
    providers = data.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("adapter catalog requires providers")
    return data


def doctor(workspace: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    reports = []
    for provider in catalog["providers"]:
        root = workspace / provider["checkout"]
        missing_files = [rel for rel in provider.get("required_files", []) if not (root / rel).exists()]
        missing_tools = [tool for tool in provider.get("required_tools", []) if shutil.which(tool) is None]
        source_ready = root.exists() and not missing_files
        runtime_ready = source_ready and not missing_tools
        reports.append({
            "provider": provider["provider"],
            "version": provider["version"],
            "checkout": provider["checkout"],
            "source_ready": source_ready,
            "runtime_ready": runtime_ready,
            "missing_files": missing_files,
            "missing_tools": missing_tools,
            "capabilities": [e["capability"] for e in provider.get("entrypoints", [])],
        })
    return {
        "schema":"chimera-doctor/v1",
        "ready": all(r["runtime_ready"] for r in reports),
        "providers": reports,
    }
