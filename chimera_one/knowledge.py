from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".rs", ".ts", ".tsx", ".js", ".mjs", ".c", ".cc", ".cpp",
    ".h", ".hpp", ".json", ".jsonl", ".toml", ".yaml", ".yml", ".proto", ".rho", ".sh"
}
MAX_FILE_BYTES = 256 * 1024
MAX_INDEX_TEXT = 24_000


def _git_files(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False
    )
    if proc.returncode != 0:
        return []
    return [p.decode("utf-8", "replace") for p in proc.stdout.split(b"\0") if p]


def classify(path: str) -> str:
    lower = path.lower()
    name = Path(lower).name
    if "/test" in lower or name.startswith("test_") or ".test." in name or ".spec." in name:
        return "test"
    if lower.startswith("docs/") or name.endswith(".md"):
        return "documentation"
    if "schema" in lower or name.endswith(".proto"):
        return "contract"
    if name in {"cargo.toml", "pyproject.toml", "package.json", "docker-compose.yml", "compose.yaml"} or lower.startswith(".github/"):
        return "configuration"
    return "source"


def build_index(workspace: Path, constellation: dict[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for repo in constellation["repositories"]:
        checkout = str(repo.get("checkout") or repo["name"])
        root = workspace / checkout
        if not (root / ".git").exists():
            continue
        for rel in _git_files(root):
            path = root / rel
            if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if len(raw) > MAX_FILE_BYTES or b"\x00" in raw:
                continue
            text = raw.decode("utf-8", "replace")
            records.append({
                "repository": repo["name"],
                "role": repo["role"],
                "path": rel,
                "kind": classify(rel),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "text": text[:MAX_INDEX_TEXT],
            })
    records.sort(key=lambda r: (r["repository"], r["path"]))
    payload: dict[str, Any] = {"schema": "chimera-knowledge-index/v1", "records": records}
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload["digest"] = hashlib.sha256(digest_input).hexdigest()
    return payload


def query(index: dict[str, Any], term: str, limit: int = 20) -> list[dict[str, Any]]:
    needle = term.casefold()
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in index.get("records", []):
        path_hits = record["path"].casefold().count(needle)
        text_fold = record.get("text", "").casefold()
        text_hits = text_fold.count(needle)
        score = path_hits * 20 + min(text_hits, 20)
        if score:
            pos = text_fold.find(needle)
            text = record.get("text", "")
            start = max(0, pos - 120) if pos >= 0 else 0
            end = min(len(text), (pos + len(term) + 220) if pos >= 0 else 300)
            item = {k: v for k, v in record.items() if k != "text"}
            item["score"] = score
            item["snippet"] = " ".join(text[start:end].split())
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["repository"], pair[1]["path"]))
    return [item for _, item in scored[:limit]]
