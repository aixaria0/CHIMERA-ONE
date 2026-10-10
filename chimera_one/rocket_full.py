from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any
import json
import os
import shutil
import subprocess

from . import rocket as base

OMEGA_SCOPE = "PINNED_ARTIFACT_TRACE_EQUALITY_ONLY"
RCHAIN_SCOPE = "DETACHED_CXP_CONTRACT_REPRODUCTION_WITH_THREE_LOCAL_PROCESSES"


class FullRocketError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FullRocketError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=dict(os.environ),
    )
    if process.returncode != 0:
        raise FullRocketError(
            "cross-repository verifier rejected: "
            + json.dumps(
                {
                    "command": command,
                    "returncode": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                }
            )
        )
    return process


def _validate_omega(report: dict[str, Any], *, expected_digest: str) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != "chimera-verification-report/v2":
        errors.append("omega_schema")
    if report.get("status") != "LOCALLY_SUPPORTED":
        errors.append("omega_status")
    if report.get("scope") != OMEGA_SCOPE:
        errors.append("omega_scope")
    if report.get("envelope_digest") != expected_digest:
        errors.append("omega_digest")
    dimensions = report.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append("omega_dimensions")
    else:
        if dimensions.get("artifact_conformance") != "CONFIRMED":
            errors.append("omega_artifact_conformance")
        if dimensions.get("negative_control") != "PASS":
            errors.append("omega_negative_control")
        for key in (
            "formal_proof",
            "implementation_binding",
            "runtime_reproduction",
            "independent_observation",
            "production_reachability",
            "finality_externality",
        ):
            if dimensions.get(key) != "UNKNOWN":
                errors.append(f"omega_{key}_promotion")
        if dimensions.get("replay") != "NOT_RUN":
            errors.append("omega_replay_promotion")
    return errors


def _run_omega(checkout: Path, envelope: Path, expected_digest: str) -> dict[str, Any]:
    if not (checkout / "Cargo.toml").is_file():
        raise FullRocketError(f"CHIMERA-OMEGA checkout not found: {checkout}")
    process = _run(
        [
            "cargo",
            "run",
            "--locked",
            "--quiet",
            "--bin",
            "omega",
            "--",
            "verify",
            str(envelope),
            "--expect",
            expected_digest,
        ],
        cwd=checkout,
        timeout=180,
    )
    try:
        report = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise FullRocketError("OMEGA output is not JSON") from exc
    if not isinstance(report, dict):
        raise FullRocketError("OMEGA report must be an object")
    errors = _validate_omega(report, expected_digest=expected_digest)
    if errors:
        raise FullRocketError(f"OMEGA report failed bounded validation: {errors}")
    return report


def _validate_rchain(summary: dict[str, Any], *, expected_digest: str) -> list[str]:
    errors: list[str] = []
    if summary.get("schema") != "quantum-cxp-assurance-run/v1":
        errors.append("rchain_schema")
    if summary.get("status") != "PASS":
        errors.append("rchain_status")
    if summary.get("scope") != RCHAIN_SCOPE:
        errors.append("rchain_scope")
    if summary.get("operation") != "quantum-cxp/v1":
        errors.append("rchain_operation")
    if summary.get("cxpSha256") != expected_digest:
        errors.append("rchain_digest")
    if summary.get("distinctProcesses") != 3:
        errors.append("rchain_processes")
    if summary.get("distinctVerifiers") != 2:
        errors.append("rchain_verifiers")
    if summary.get("reportStatus") != "PASS" or summary.get("reportCode") != "VERIFIED":
        errors.append("rchain_report")
    if summary.get("reviewerStatus") != "PASS":
        errors.append("rchain_reviewer")
    process_ids = summary.get("processIds")
    verifier_ids = summary.get("verifierActorIds")
    if not isinstance(process_ids, list) or len(set(process_ids)) != 3:
        errors.append("rchain_process_identity")
    if not isinstance(verifier_ids, list) or len(set(verifier_ids)) != 2:
        errors.append("rchain_verifier_identity")
    return errors


def _run_rchain(checkout: Path, cxp_run: Path, output_dir: Path) -> dict[str, Any]:
    script = checkout / "scripts" / "quantum-cxp-assurance.mjs"
    if not script.is_file():
        raise FullRocketError(
            "RCHAIN-COMPLIER checkout does not expose quantum-cxp-assurance.mjs; "
            "use quantum-cxp-assurance-v1"
        )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    process = _run(
        [
            "node",
            "--experimental-strip-types",
            str(script),
            str(cxp_run),
            str(output_dir),
        ],
        cwd=checkout,
        timeout=120,
    )
    summary_path = output_dir / "summary.json"
    if not summary_path.is_file():
        raise FullRocketError(
            "RCHAIN-COMPLIER assurance runner did not retain summary.json; "
            f"stdout={process.stdout!r}"
        )
    return _read_json(summary_path)


def _augment_certificate(
    root: Path,
    *,
    workspace: Path,
    omega_report: dict[str, Any],
    rchain_summary: dict[str, Any],
) -> dict[str, Any]:
    cert = _read_json(root / "rocket-certificate.json")
    run = _read_json(root / "chimera-run-v2.json")
    omega = workspace / "CHIMERA-OMEGA"
    rchain = workspace / "RCHAIN-COMPLIER"
    cert["verification"]["omega_kernel"] = "CONFIRMED"
    cert["verification"]["rchain_assurance_engine"] = "CONFIRMED"
    cert["verification"]["rchain_three_processes"] = "CONFIRMED"
    cert["verification"]["rchain_two_verifier_receipts"] = "CONFIRMED"
    cert["evidence_engines"] = {
        "omega": {
            "repository": "aixaria0/CHIMERA-OMEGA",
            "revision": base._revision(omega),
            "envelope_digest": omega_report["envelope_digest"],
            "scope": omega_report["scope"],
            "status": omega_report["status"],
        },
        "rchain_complier": {
            "repository": "aixaria0/RCHAIN-COMPLIER",
            "revision": base._revision(rchain),
            "cxp_sha256": rchain_summary["cxpSha256"],
            "scope": rchain_summary["scope"],
            "status": rchain_summary["status"],
            "distinct_processes": rchain_summary["distinctProcesses"],
            "distinct_verifiers": rchain_summary["distinctVerifiers"],
        },
    }
    cert["authority"]["omega_artifact_conformance"] = "CONFIRMED"
    cert["authority"]["rchain_local_process_assurance"] = "CONFIRMED"
    cert["authority"]["host_independence"] = "UNKNOWN"
    cert["authority"]["organizational_independence"] = "UNKNOWN"
    cert["authority"]["external_truth"] = "UNKNOWN"
    cert["scope"] = (
        "CXP_V1_QUANTUM_EXECUTION_OMEGA_KERNEL_RCHAIN_ASSURANCE_"
        "PLUS_LOCAL_4_PROCESS_LOOPBACK_PBFT_FINALITY"
    )
    cert["rocket_sha256"] = ""
    cert["rocket_sha256"] = base._rocket_digest(cert)
    if cert["cxp_sha256"] != run["cxp_sha256"]:
        raise FullRocketError("Rocket/CXP binding changed during augmentation")
    _write_json(root / "rocket-certificate.json", cert)
    return cert


def run_objective(objective: Path, *, workspace: Path, output: Path) -> dict[str, Any]:
    cert = base.run_objective(objective, workspace=workspace, output=output)
    del cert
    run = _read_json(output / "chimera-run-v2.json")
    provider = output / "provider"
    omega_checkout = (workspace / "CHIMERA-OMEGA").resolve()
    rchain_checkout = (workspace / "RCHAIN-COMPLIER").resolve()

    omega_report = _run_omega(
        omega_checkout,
        provider / "omega-envelope.json",
        str(run["evidence"]["omega_envelope_digest"]),
    )
    _write_json(output / "omega-report.json", omega_report)

    rchain_dir = output / "rchain-assurance"
    rchain_summary = _run_rchain(rchain_checkout, output / "chimera-run-v2.json", rchain_dir)
    rchain_errors = _validate_rchain(rchain_summary, expected_digest=str(run["cxp_sha256"]))
    if rchain_errors:
        raise FullRocketError(f"RCHAIN-COMPLIER report failed bounded validation: {rchain_errors}")

    return _augment_certificate(
        output,
        workspace=workspace,
        omega_report=omega_report,
        rchain_summary=rchain_summary,
    )


def verify_run(root: Path, *, workspace: Path) -> dict[str, Any]:
    base_report = base.verify_run(root, workspace=workspace)
    errors = list(base_report["errors"])
    run = _read_json(root / "chimera-run-v2.json")
    cert = _read_json(root / "rocket-certificate.json")
    provider = root / "provider"

    try:
        saved_omega = _read_json(root / "omega-report.json")
        errors.extend(
            _validate_omega(
                saved_omega,
                expected_digest=str(run["evidence"]["omega_envelope_digest"]),
            )
        )
        reproduced_omega = _run_omega(
            (workspace / "CHIMERA-OMEGA").resolve(),
            provider / "omega-envelope.json",
            str(run["evidence"]["omega_envelope_digest"]),
        )
        errors.extend(
            _validate_omega(
                reproduced_omega,
                expected_digest=str(run["evidence"]["omega_envelope_digest"]),
            )
        )
    except (FullRocketError, OSError, json.JSONDecodeError, subprocess.SubprocessError):
        errors.append("omega_reproduction")

    try:
        saved_rchain = _read_json(root / "rchain-assurance" / "summary.json")
        errors.extend(_validate_rchain(saved_rchain, expected_digest=str(run["cxp_sha256"])))
        reproduced_dir = root / ".verify-rchain-assurance"
        reproduced = _run_rchain(
            (workspace / "RCHAIN-COMPLIER").resolve(),
            root / "chimera-run-v2.json",
            reproduced_dir,
        )
        errors.extend(_validate_rchain(reproduced, expected_digest=str(run["cxp_sha256"])))
        shutil.rmtree(reproduced_dir, ignore_errors=True)
    except (FullRocketError, OSError, json.JSONDecodeError, subprocess.SubprocessError):
        errors.append("rchain_reproduction")

    engines = cert.get("evidence_engines")
    if not isinstance(engines, dict):
        errors.append("evidence_engines")
    else:
        if engines.get("omega", {}).get("status") != "LOCALLY_SUPPORTED":
            errors.append("certificate_omega_binding")
        if engines.get("rchain_complier", {}).get("status") != "PASS":
            errors.append("certificate_rchain_binding")
    if cert.get("authority", {}).get("host_independence") != "UNKNOWN":
        errors.append("host_independence_promotion")
    if cert.get("authority", {}).get("organizational_independence") != "UNKNOWN":
        errors.append("organizational_independence_promotion")
    if cert.get("authority", {}).get("external_truth") != "UNKNOWN":
        errors.append("external_truth_promotion")
    if cert.get("rocket_sha256") != base._rocket_digest(cert):
        errors.append("rocket_digest")

    return {
        **base_report,
        "schema": "chimera-rocket-full-verification/v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "omega_kernel": "CONFIRMED" if "omega_reproduction" not in errors else "NOT_CONFIRMED",
        "rchain_assurance_engine": "CONFIRMED" if "rchain_reproduction" not in errors else "NOT_CONFIRMED",
        "external_truth": "UNKNOWN",
    }


def main() -> int:
    parser = ArgumentParser(
        prog="chimera-rocket",
        description="Bounded CHIMERA CXP execution fabric with actual OMEGA/RCHAIN/Sovereign engines",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("objective")
    run.add_argument("--workspace", default="..")
    run.add_argument("--output", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("path")
    verify.add_argument("--workspace", default="..")

    args = parser.parse_args()
    try:
        workspace = Path(args.workspace).resolve()
        if args.command == "run":
            result = run_objective(
                Path(args.objective).resolve(),
                workspace=workspace,
                output=Path(args.output).resolve(),
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("status") == "ASSURED" else 2
        result = verify_run(Path(args.path).resolve(), workspace=workspace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 2
    except (
        FullRocketError,
        base.RocketError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {"schema": "chimera-rocket-error/v1", "status": "REJECTED", "error": str(exc)},
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
