from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .catalog import load_catalog
from .doctor import doctor, load_adapters
from .federation import federation_report
from .knowledge import build_index, query
from .plan import build_plan
from .workspace import build_snapshot, load_constellation


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _workspace(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    env = os.getenv("CHIMERA_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    return _root().parent


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_status(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(_workspace(args.workspace), _root() / "docs" / "CONSTELLATION.json")
    if args.output:
        _write_json(Path(args.output), snapshot)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    bad = [r for r in snapshot["repositories"] if not r["exists"] or not r["is_git"] or r.get("origin_matches") is False]
    return 2 if bad else 0


def cmd_capabilities(_: argparse.Namespace) -> int:
    caps = load_catalog(_root() / "capabilities" / "catalog.json")
    print(json.dumps([cap.raw for cap in caps], indent=2, sort_keys=True))
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    constellation = load_constellation(_root() / "docs" / "CONSTELLATION.json")
    index = build_index(_workspace(args.workspace), constellation)
    out = Path(args.output or (_root() / ".chimera" / "knowledge-index.json"))
    _write_json(out, index)
    summary = {
        "schema": index["schema"],
        "digest": index["digest"],
        "records": len(index["records"]),
        "output": str(out),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    path = Path(args.index or (_root() / ".chimera" / "knowledge-index.json"))
    if not path.exists():
        raise SystemExit(f"knowledge index does not exist: {path}; run 'chimera-one index' first")
    data = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(query(data, args.term, args.limit), indent=2, sort_keys=True))
    return 0


def cmd_federation(args: argparse.Namespace) -> int:
    constellation = load_constellation(_root() / "docs" / "CONSTELLATION.json")
    caps = load_catalog(_root() / "capabilities" / "catalog.json")
    report = federation_report(_workspace(args.workspace), constellation, caps)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 2


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor(_workspace(args.workspace), load_adapters(_root() / "adapters" / "catalog.json"))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


def cmd_plan(args: argparse.Namespace) -> int:
    caps = load_catalog(_root() / "capabilities" / "catalog.json")
    plan = build_plan(args.objective, args.domain, caps)
    if args.output:
        _write_json(Path(args.output), plan)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chimera-one", description="CHIMERA-ONE constellation control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="snapshot repository identities and Git state")
    status.add_argument("--workspace")
    status.add_argument("--output")
    status.set_defaults(func=cmd_status)

    caps = sub.add_parser("capabilities", help="print validated capability catalog")
    caps.set_defaults(func=cmd_capabilities)

    index = sub.add_parser("index", help="build a bounded local knowledge index from tracked text files")
    index.add_argument("--workspace")
    index.add_argument("--output")
    index.set_defaults(func=cmd_index)

    search = sub.add_parser("query", help="search the local knowledge index")
    search.add_argument("term")
    search.add_argument("--index")
    search.add_argument("--limit", type=int, default=20)
    search.set_defaults(func=cmd_query)

    federation = sub.add_parser("federation", help="validate provider-owned manifests against the central constellation and capability registry")
    federation.add_argument("--workspace")
    federation.set_defaults(func=cmd_federation)

    doctor_parser = sub.add_parser("doctor", help="check whether each declared provider is actually callable on this machine")
    doctor_parser.add_argument("--workspace")
    doctor_parser.set_defaults(func=cmd_doctor)

    plan = sub.add_parser("plan", help="compile an objective into a bounded cross-repository execution DAG")
    plan.add_argument("objective")
    plan.add_argument("--domain", choices=["general", "rchain-audit"], default="general")
    plan.add_argument("--output")
    plan.set_defaults(func=cmd_plan)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
