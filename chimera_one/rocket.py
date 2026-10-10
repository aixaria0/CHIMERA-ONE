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

from .cxp_v2 import canonical_bytes, load_run, validate_run_v2

ROCKET_SCHEMA = "chimera-rocket-certificate/v1"
ROCKET_DOMAIN = b"CHIMERA-ROCKET\0certificate/v1\0"
QUANTUM_ADAPTER = "quantum001-elevator/v1"


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


def _rocket_digest(certificate: dict[str, Any]) -> str:
    body = dict(certificate)
    body.pop("rocket_sha256", None)
    h = hashlib.sha256()
    h.update(ROCKET_DOMAIN)
    h.update(canonical_bytes(body))
    return h.hexdigest()


def _build_rocket_certificate(run: dict[str, Any], *, quantum_revision: str, control_plane_revision: str) -> dict[str, Any]:
    cert: dict[str, Any] = {
        "schema": ROCKET_SCHEMA,
        "status": run["certificate"]["status"],
        "scope": "CXP_V1_BOUNDED_QUANTUM001_EXECUTION_IMPORT_AND_CONTROL_PLANE_VALIDATION",
        "run_id": run["run_id"],
        "cxp_sha256": run["cxp_sha256"],
        "provider": "aixaria0/Quantum001",
        "provider_revision": quantum_revision,
        "provider_certificate_sha256": run["evidence"]["provider_certificate_sha256"],
        "control_plane": "aixaria0/CHIMERA-ONE",
        "control_plane_revision": control_plane_revision,
        "verification": {
            "cxp_contract": "CONFIRMED",
            "provider_certificate_signature": "CONFIRMED",
            "two_process_quorum": run["authority"]["two_process_quorum"],
            "replay": run["verification"]["replay"],
        },
        "authority": {
            "local_execution": run["authority"]["local_execution"],
            "signed_execution": run["authority"]["signed_execution"],
            "distributed_consensus": run["authority"]["distributed_consensus"],
            "qpu_execution": run["authority"]["qpu_execution"],
            "hardware_attestation": run["authority"]["hardware_attestation"],
            "external_truth": "UNKNOWN",
        },
        "limitations": [
            "The control-plane certificate is content-addressed but is not separately signed in Rocket V1.",
            "Quantum001 local process/key independence does not establish independent hosts or organizations.",
            "Sovereign-Lattice consensus is not executed by this V1 adapter.",
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


def run_objective(objective_path: Path, *, workspace: Path, output: Path) -> dict[str, Any]:
    objective = _read_json(objective_path)
    _validate_objective(objective)

    quantum = (workspace / "Quantum001").resolve()
    if not (quantum / "chimera_quantum" / "elevator.py").is_file():
        raise RocketError(f"Quantum001 checkout with elevator contract not found: {quantum}")
    if not (quantum / "run_cxp_export.py").is_file():
        raise RocketError("Quantum001 checkout does not expose CXP export; use the cxp-v1-export contract revision")

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

    copied_run = output / "chimera-run-v2.json"
    shutil.copyfile(provider_run, copied_run)
    certificate = _build_rocket_certificate(
        run,
        quantum_revision=_revision(quantum),
        control_plane_revision=_revision(Path(__file__).resolve().parent.parent),
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

    quantum = (workspace / "Quantum001").resolve()
    try:
        _verify_quantum001_certificate(quantum, root / "provider" / "final-certificate.json")
    except (RocketError, OSError, subprocess.SubprocessError):
        errors.append("provider_signature")

    provider_cert = _read_json(root / "provider" / "final-certificate.json")
    if provider_cert.get("certificate_sha256") != cert.get("provider_certificate_sha256"):
        errors.append("provider_digest")

    return {
        "schema": "chimera-rocket-verification/v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "run_id": run.get("run_id"),
        "cxp_sha256": run.get("cxp_sha256"),
        "rocket_sha256": cert.get("rocket_sha256"),
    }


def main() -> int:
    parser = ArgumentParser(prog="chimera-rocket", description="Bounded CHIMERA CXP execution fabric")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="execute one bounded CXP objective through Quantum001")
    run.add_argument("objective")
    run.add_argument("--workspace", default="..")
    run.add_argument("--output", required=True)

    verify = sub.add_parser("verify", help="verify a saved Rocket V1 run")
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
