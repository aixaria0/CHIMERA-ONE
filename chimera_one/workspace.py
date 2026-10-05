from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def _normalize_remote(value: str) -> str:
    value = value.strip().removesuffix(".git")
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value[len("git@github.com:"):]
    return value.rstrip("/")


@dataclass(frozen=True)
class RepoStatus:
    name: str
    role: str
    url: str
    checkout: str
    exists: bool
    is_git: bool
    branch: str | None = None
    head: str | None = None
    dirty: bool | None = None
    origin: str | None = None
    origin_matches: bool | None = None
    tracked_files: int | None = None


def load_constellation(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "chimera-constellation/v1":
        raise ValueError("unsupported constellation schema")
    repos = data.get("repositories")
    if not isinstance(repos, list) or not repos:
        raise ValueError("constellation requires repositories")
    return data


def inspect_workspace(workspace: Path, constellation: dict[str, Any]) -> list[RepoStatus]:
    statuses: list[RepoStatus] = []
    for item in constellation["repositories"]:
        checkout = str(item.get("checkout") or item["name"])
        path = workspace / checkout
        base = dict(name=str(item["name"]), role=str(item["role"]), url=str(item["url"]), checkout=checkout)
        if not path.exists():
            statuses.append(RepoStatus(**base, exists=False, is_git=False))
            continue
        if not (path / ".git").exists():
            statuses.append(RepoStatus(**base, exists=True, is_git=False))
            continue
        try:
            branch = _git(path, "branch", "--show-current") or None
            head = _git(path, "rev-parse", "HEAD")
            dirty = bool(_git(path, "status", "--porcelain"))
            origin = _git(path, "remote", "get-url", "origin")
            tracked = _git(path, "ls-files")
            tracked_files = len(tracked.splitlines()) if tracked else 0
            statuses.append(RepoStatus(
                **base, exists=True, is_git=True, branch=branch, head=head, dirty=dirty,
                origin=origin, origin_matches=_normalize_remote(origin) == _normalize_remote(str(item["url"])),
                tracked_files=tracked_files,
            ))
        except RuntimeError:
            statuses.append(RepoStatus(**base, exists=True, is_git=True))
    return statuses


def build_snapshot(workspace: Path, constellation_path: Path) -> dict[str, Any]:
    constellation = load_constellation(constellation_path)
    repos = [asdict(status) for status in inspect_workspace(workspace, constellation)]
    payload = {
        "schema": "chimera-constellation-snapshot/v1",
        "repositories": repos,
    }
    payload["digest"] = sha256_json(payload)
    return payload
