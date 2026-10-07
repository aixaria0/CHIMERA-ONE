from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from .catalog import load_catalog
from .capture_attestation import attest_capture, verify_capture_attestation
from .doctor import doctor, load_adapters
from .federation import federation_report
from .knowledge import build_index, query
from .offline_review import ReviewError, review_aether_history, validate_capture
from .plan import build_plan
from .protocol import load_json as load_protocol_json, protocol_digest, validate_run
from .workspace import build_snapshot, load_constellation


def _root() -> Path:
    override = os.getenv("CHIMERA_ONE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
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



def cmd_protocol_digest(args: argparse.Namespace) -> int:
    value = load_protocol_json(args.path)
    print(protocol_digest(value))
    return 0


def cmd_protocol_validate(args: argparse.Namespace) -> int:
    report = validate_run(load_protocol_json(args.path))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 3


def cmd_review_history(args: argparse.Namespace) -> int:
    try:
        receipt = review_aether_history(
            checkout=Path(args.omega_checkout), binary=Path(args.omega_bin),
            expected_binary=args.expect_omega_binary, export=Path(args.export),
            registry=Path(args.registry), context=Path(args.context),
            expected_context=args.expect_context, output=Path(args.output))
    except (ReviewError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}))
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return {"CONFIRMED": 0, "REJECTED": 2, "BLOCKED": 3}[receipt["invocation"]["outcome"]]


def cmd_validate_capture(args: argparse.Namespace) -> int:
    try:
        report = validate_capture(Path(args.path), args.expect_receipt)
    except (ReviewError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def cmd_attest_capture(args: argparse.Namespace) -> int:
    try:
        report = attest_capture(root=Path(args.path), expected_receipt=args.expect_receipt,
                                private_key=Path(args.key), signer_id=args.signer_id,
                                expected_key=args.expect_key, output=Path(args.output))
    except (ReviewError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def cmd_verify_attestation(args: argparse.Namespace) -> int:
    try:
        report = verify_capture_attestation(root=Path(args.path), attestation=Path(args.attestation),
                                            expected_receipt=args.expect_receipt,
                                            expected_key=args.expect_key,
                                            expected_signer=args.expect_signer)
    except (ReviewError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
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

    digest = sub.add_parser("protocol-digest", help="compute the canonical domain-separated protocol digest of JSON")
    digest.add_argument("path")
    digest.set_defaults(func=cmd_protocol_digest)

    validate = sub.add_parser("protocol-validate", help="fail-closed validation of a chimera-run/v1 record")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_protocol_validate)

    review = sub.add_parser("review-aether-history", help="run one pinned offline OMEGA verifier and retain its exact report")
    review.add_argument("--omega-checkout", required=True)
    review.add_argument("--omega-bin", required=True)
    review.add_argument("--expect-omega-binary", required=True)
    review.add_argument("--export", required=True)
    review.add_argument("--registry", required=True)
    review.add_argument("--context", required=True)
    review.add_argument("--expect-context", required=True)
    review.add_argument("--output", required=True)
    review.set_defaults(func=cmd_review_history)

    capture = sub.add_parser("validate-capture", help="check saved capture bytes under an independently selected receipt pin; no provider rerun")
    capture.add_argument("path")
    capture.add_argument("--expect-receipt", required=True)
    capture.set_defaults(func=cmd_validate_capture)

    attest = sub.add_parser("attest-capture", help="sign a pinned saved capture with an explicit local Ed25519 key")
    attest.add_argument("path")
    attest.add_argument("--expect-receipt", required=True)
    attest.add_argument("--key", required=True)
    attest.add_argument("--signer-id", required=True)
    attest.add_argument("--expect-key", required=True)
    attest.add_argument("--output", required=True)
    attest.set_defaults(func=cmd_attest_capture)

    attested = sub.add_parser("verify-capture-attestation", help="verify saved bytes and signature under externally selected receipt, key and signer pins")
    attested.add_argument("path")
    attested.add_argument("--attestation", required=True)
    attested.add_argument("--expect-receipt", required=True)
    attested.add_argument("--expect-key", required=True)
    attested.add_argument("--expect-signer", required=True)
    attested.set_defaults(func=cmd_verify_attestation)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
