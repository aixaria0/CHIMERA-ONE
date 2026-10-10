from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import shutil
import subprocess
import sys

from .cxp_v2 import canonical_bytes, validate_run_v2

ROCKET_SCHEMA = "chimera-rocket-certificate/v1"
ROCKET_DOMAIN = b"CHIMERA-ROCKET\0certificate/v1\0"
QUANTUM_ADAPTER = "quantum001-elevator/v1"
SOVEREIGN_SCHEMA = "sovereign-cxp-local-quorum/v1"
SOVEREIGN_SCOPE = "LOCAL_IN_PROCESS_PBFT_QUORUM"


class RocketError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RocketError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _revision(checkout: Path) -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True, capture_output=True, timeout=5, check=False
    )
    if process.returncode != 0:
        raise RocketError(f"cannot resolve git revision for {checkout}: {process.stderr.strip()}")
    return process.stdout.strip()


def _python_env(checkout: Path) -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(checkout) if not existing else str(checkout) + os.pathsep + existing
    return env


def _run_fixed(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout, check=False)
    if process.returncode != 0:
        raise RocketError(
            "bounded adapter command failed: "
            + json.dumps({"command": command, "returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
        )
    return process


def _verify_quantum001_certificate(checkout: Path, certificate: Path) -> None:
    script = (
        "import json,sys; "
        "from chimera_quantum.assurance import verify_final_certificate; "
        "v=json.load(open(sys.argv[1],encoding='utf-8')); "
        "raise SystemExit(0 if verify_final_certificate(v) else 2)"
    )
    _run_fixed([sys.executable, "-c", script, str(certificate)], cwd=checkout, env=_python_env(checkout), timeout=20)


def _validate_local_quorum(report: dict[str, Any], expected_digest: str) -> list[str]:
    errors: list[str] = []
    if report.get("schema") != SOVEREIGN_SCHEMA:
        errors.append("sovereign_schema")
    if report.get("status") != "CONFIRMED":
        errors.append("sovereign_status")
    if report.get("scope") != SOVEREIGN_SCOPE:
        errors.append("sovereign_scope")
    if report.get("digest_sha256") != expected_digest:
        errors.append("sovereign_digest_binding")
    if report.get("total_nodes") != 4 or report.get("fault_tolerance") != 1 or report.get("quorum_size") != 3:
        errors.append("sovereign_quorum_shape")
    if report.get("prepared_certificate") != "CONFIRMED":
        errors.append("sovereign_prepare_certificate")
    if report.get("commit_certificate") != "CONFIRMED" or report.get("commit_certificate_verified") is not True:
        errors.append("sovereign_commit_certificate")
    if report.get("signer_ids") != [0, 1, 2]:
        errors.append("sovereign_signers")
    if report.get("process_independence") != "UNKNOWN" or report.get("host_independence") != "UNKNOWN":
        errors.append("sovereign_independence_promotion")
    if report.get("network_transport") != "NOT_RUN" or report.get("distributed_finality") != "UNKNOWN":
        errors.append("sovereign_finality_promotion")
    commitment = report.get("certificate_commitment_sha256")
    if not isinstance(commitment, str) or len(commitment) != 64:
        errors.append("sovereign_certificate_commitment")
    return errors


def _run_sovereign_quorum(checkout: Path, digest: str) -> dict[str, Any]:
    manifest = checkout / "rust_engine" / "Cargo.toml"
    source = checkout / "rust_engine" / "src" / "bin" / "cxp_finalizer.rs"
    if not manifest.is_file() or not source.is_file():
        raise RocketError("Sovereign-Lattice checkout does not expose cxp_finalizer; use cxp-local-quorum-v1 contract revision")
    process = _run_fixed(
        [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(manifest),
            "--bin",
            "cxp_finalizer",
            "--",
            digest,
        ],
        cwd=checkout,
        timeout=180,
    )
    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        raise RocketError("Sovereign-Lattice finalizer produced no JSON output")
    try:
        report = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RocketError("Sovereign-Lattice finalizer output is not JSON") from exc
    if not isinstance(report, dict):
        raise RocketError("Sovereign-Lattice finalizer output must be an object")
    errors = _validate_local_quorum(report, digest)
    if errors:
        raise RocketError(f"Sovereign-Lattice local quorum validation failed: {errors}")
    return report


def _rocket_digest(certificate: dict[str, Any]) -> str:
    body = dict(certificate)
    body.pop("rocket_sha256", None)
    h = hashlib.sha256()
    h.update(ROCKET_DOMAIN)
    h.update(canonical_bytes(body))
    return h.hexdigest()


def _build_rocket_certificate(
    run: dict[str, Any],
    *,
    quantum_revision: str,
    control_plane_revision: str,
    sovereign_revision: str,
    consensus_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    commitments = [str(report["certificate_commitment_sha256"]) for report in consensus_reports]
    cert: dict[str, Any] = {
        "schema": ROCKET_SCHEMA,
        "status": run["certificate"]["status"],
        "scope": "CXP_V1_BOUNDED_QUANTUM_EXECUTION_ASSURANCE_AND_REPRODUCED_LOCAL_PBFT_QUORUM",
        "run_id": run["run_id"],
        "cxp_sha256": run["cxp_sha256"],
        "provider": "aixaria0/Quantum001",
        "provider_revision": quantum_revision,
        "provider_certificate_sha256": run["evidence"]["provider_certificate_sha256"],
        "control_plane": "aixaria0/CHIMERA-ONE",
        "control_plane_revision": control_plane_revision,
        "consensus": {
            "provider": "aixaria0/Sovereign-Lattice",
            "provider_revision": sovereign_revision,
            "scope": SOVEREIGN_SCOPE,
            "bound_digest_sha256": run["cxp_sha256"],
            "local_pbft_quorum": "CONFIRMED",
            "local_quorum_reproductions": len(consensus_reports),
            "certificate_commitments_sha256": commitments,
            "process_independence": "UNKNOWN",
            "host_independence": "UNKNOWN",
            "network_transport": "NOT_RUN",
            "distributed_finality": "UNKNOWN",
        },
        "verification": {
            "cxp_contract": "CONFIRMED",
            "provider_certificate_signature": "CONFIRMED",
            "two_process_quorum": run["authority"]["two_process_quorum"],
            "replay": run["verification"]["replay"],
            "local_pbft_quorum": "CONFIRMED",
            "local_pbft_quorum_reproduced": "CONFIRMED" if len(consensus_reports) >= 2 else "NOT_CONFIRMED",
        },
        "authority": {
            "local_execution": run["authority"]["local_execution"],
            "signed_execution": run["authority"]["signed_execution"],
            "local_pbft_quorum": "CONFIRMED",
            "distributed_consensus": "NOT_RUN",
            "distributed_finality": "UNKNOWN",
            "qpu_execution": run["authority"]["qpu_execution"],
            "hardware_attestation": run["authority"]["hardware_attestation"],
            "external_truth": "UNKNOWN",
        },
        "limitations": [
            "The control-plane certificate is content-addressed but is not separately signed in Rocket V1.",
            "Quantum001 local process/key independence does not establish independent hosts or organizations.",
            "Sovereign-Lattice PBFT quorum is reproduced in separate local processes, but each reproduction creates all four threshold shares inside one process.",
            "Local PBFT quorum is not promoted to network or distributed finality.",
            "QPU execution remains UNKNOWN unless separately evidenced by the provider run.",
        ],
        "rocket_sha256": "",
    }
    cert["rocket_sha256"] = _rocket_digest(cert)
    return cert


def _validate_objective(value: dict[str, Any]) -> None:
    if value.get("schema") != "chimera-objective/v1":
        raise RocketError("objective schema must be chimera-objective/v1")
    if value.get("adapter") != QUANTUM_ADAPTER:
        raise RocketError(f"Rocket V1 only authorizes adapter {QUANTUM_ADAPTER}")
    if value.get("domain") != "quantum":
        raise RocketError("Rocket V1 adapter requires domain=quantum")
    if not isinstance(value.get("objective"), str) or not value["objective"].strip():
        raise RocketError("objective text is required")
    seed = value.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise RocketError("seed must be an unsigned 32-bit integer")
    if value.get("local_pbft_quorum", True) is not True:
        raise RocketError("Rocket V1 requires local_pbft_quorum=true")


def run_objective(objective_path: Path, *, workspace: Path, output: Path) -> dict[str, Any]:
    objective = _read_json(objective_path)
    _validate_objective(objective)

    quantum = (workspace / "Quantum001").resolve()
    sovereign = (workspace / "Sovereign-Lattice").resolve()
    if not (quantum / "chimera_quantum" / "elevator.py").is_file():
        raise RocketError(f"Quantum001 checkout with elevator contract not found: {quantum}")
    if not (quantum / "run_cxp_export.py").is_file():
        raise RocketError("Quantum001 checkout does not expose CXP export; use the cxp-v1-export contract revision")
    if not (sovereign / "rust_engine" / "src" / "bin" / "cxp_finalizer.rs").is_file():
        raise RocketError("Sovereign-Lattice checkout does not expose local CXP quorum; use cxp-local-quorum-v1 contract revision")

    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RocketError(f"output directory must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    provider = output / "provider"

    seed = int(objective.get("seed", 42))
    env = _python_env(quantum)
    _run_fixed(
        [sys.executable, "-m", "chimera_quantum.elevator", "--workspace", str(provider), "--seed", str(seed)],
        cwd=quantum,
        env=env,
        timeout=90,
    )
    provider_run = provider / "chimera-run-v2.json"
    _run_fixed(
        [sys.executable, "run_cxp_export.py", "--workspace", str(provider), "--output", str(provider_run), "--objective", objective["objective"]],
        cwd=quantum,
        env=env,
        timeout=30,
    )

    run = _read_json(provider_run)
    report = validate_run_v2(run)
    if not report["valid"]:
        raise RocketError(f"CXP validation failed: {report['errors']}")

    final_certificate = provider / "final-certificate.json"
    _verify_quantum001_certificate(quantum, final_certificate)
    provider_cert = _read_json(final_certificate)
    if run["evidence"]["provider_certificate_sha256"] != provider_cert.get("certificate_sha256"):
        raise RocketError("CXP/provider certificate digest mismatch")

    consensus_a = _run_sovereign_quorum(sovereign, str(run["cxp_sha256"]))
    consensus_b = _run_sovereign_quorum(sovereign, str(run["cxp_sha256"]))
    _write_json(output / "consensus-a.json", consensus_a)
    _write_json(output / "consensus-b.json", consensus_b)

    copied_run = output / "chimera-run-v2.json"
    shutil.copyfile(provider_run, copied_run)
    certificate = _build_rocket_certificate(
        run,
        quantum_revision=_revision(quantum),
        control_plane_revision=_revision(Path(__file__).resolve().parent.parent),
        sovereign_revision=_revision(sovereign),
        consensus_reports=[consensus_a, consensus_b],
    )
    _write_json(output / "rocket-certificate.json", certificate)
    _write_json(output / "objective.json", objective)
    return certificate


def verify_run(root: Path, *, workspace: Path) -> dict[str, Any]:
    root = root.resolve()
    run = _read_json(root / "chimera-run-v2.json")
    cert = _read_json(root / "rocket-certificate.json")
    report = validate_run_v2(run)
    errors = list(report["errors"])

    if cert.get("schema") != ROCKET_SCHEMA:
        errors.append("rocket_schema")
    if cert.get("rocket_sha256") != _rocket_digest(cert):
        errors.append("rocket_digest")
    if cert.get("cxp_sha256") != run.get("cxp_sha256"):
        errors.append("rocket_cxp_binding")
    if cert.get("provider_certificate_sha256") != run.get("evidence", {}).get("provider_certificate_sha256"):
        errors.append("rocket_provider_binding")
    if cert.get("authority", {}).get("external_truth") != "UNKNOWN":
        errors.append("external_truth_promotion")
    if cert.get("authority", {}).get("distributed_finality") != "UNKNOWN":
        errors.append("distributed_finality_promotion")

    quantum = (workspace / "Quantum001").resolve()
    sovereign = (workspace / "Sovereign-Lattice").resolve()
    try:
        _verify_quantum001_certificate(quantum, root / "provider" / "final-certificate.json")
    except (RocketError, OSError, subprocess.SubprocessError):
        errors.append("provider_signature")

    provider_cert = _read_json(root / "provider" / "final-certificate.json")
    if provider_cert.get("certificate_sha256") != cert.get("provider_certificate_sha256"):
        errors.append("provider_digest")

    for name in ("consensus-a.json", "consensus-b.json"):
        try:
            saved_consensus = _read_json(root / name)
            errors.extend(_validate_local_quorum(saved_consensus, str(run.get("cxp_sha256", ""))))
        except (OSError, json.JSONDecodeError, RocketError):
            errors.append("saved_sovereign_quorum")

    try:
        reproduced = _run_sovereign_quorum(sovereign, str(run.get("cxp_sha256", "")))
        errors.extend(_validate_local_quorum(reproduced, str(run.get("cxp_sha256", ""))))
    except (RocketError, OSError, subprocess.SubprocessError):
        errors.append("sovereign_quorum_reproduction")

    consensus = cert.get("consensus", {})
    if consensus.get("bound_digest_sha256") != run.get("cxp_sha256"):
        errors.append("consensus_cxp_binding")
    if consensus.get("distributed_finality") != "UNKNOWN":
        errors.append("consensus_finality_promotion")

    return {
        "schema": "chimera-rocket-verification/v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "run_id": run.get("run_id"),
        "cxp_sha256": run.get("cxp_sha256"),
        "rocket_sha256": cert.get("rocket_sha256"),
        "local_pbft_quorum": "CONFIRMED" if not errors else "NOT_CONFIRMED",
        "distributed_finality": "UNKNOWN",
    }


def main() -> int:
    parser = ArgumentParser(prog="chimera-rocket", description="Bounded CHIMERA CXP execution fabric")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="execute one bounded CXP objective through Quantum001 and local Sovereign PBFT quorum")
    run.add_argument("objective")
    run.add_argument("--workspace", default="..")
    run.add_argument("--output", required=True)

    verify = sub.add_parser("verify", help="verify a saved Rocket V1 run and reproduce its local PBFT quorum")
    verify.add_argument("path")
    verify.add_argument("--workspace", default="..")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run_objective(Path(args.objective), workspace=Path(args.workspace).resolve(), output=Path(args.output))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["status"] in {"ASSURED", "FINALIZED"} else 2
        result = verify_run(Path(args.path), workspace=Path(args.workspace).resolve())
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 2
    except (RocketError, OSError, json.JSONDecodeError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema": "chimera-rocket-error/v1", "status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
