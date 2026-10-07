#!/usr/bin/env python3
"""Real owned OMEGA CLI + ONE capture; saved fixtures only, no operational target."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from chimera_one.catalog import load_catalog
from chimera_one.federation import federation_report
from chimera_one.offline_review import OMEGA_REVISION, omega_digest, receipt_digest


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        while part := source.read(131072):
            h.update(part)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omega-checkout", type=Path, required=True)
    parser.add_argument("--omega-bin", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out = args.out.resolve()
    checkout, binary = args.omega_checkout.resolve(strict=True), args.omega_bin.resolve(strict=True)
    args.out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(PROJECT), CHIMERA_ONE_ROOT=str(PROJECT))
    binary_pin = sha(binary)  # CI/local build selection; not a production trust channel.

    def cli(arguments, expected_exit):
        result = subprocess.run([sys.executable, "-m", "chimera_one", *arguments],
                                cwd=PROJECT, env=env, capture_output=True, text=True, timeout=40)
        assert result.returncode == expected_exit, (arguments[0], result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout)

    def invoke(name, paths, pin, code, selected_binary=binary_pin):
        before = {role: p.read_bytes() for role, p in paths.items()}
        report = cli(["review-aether-history", "--omega-checkout", str(checkout),
                      "--omega-bin", str(binary), "--expect-omega-binary", selected_binary,
                      "--export", str(paths["export"]), "--registry", str(paths["registry"]),
                      "--context", str(paths["context"]), "--expect-context", pin,
                      "--output", str(args.out / name)], code)
        assert before == {role: p.read_bytes() for role, p in paths.items()}, "original artifact changed"
        return report

    sources = {}
    retained = {}
    for name in ("replay", "retired-view"):
        root = checkout / "examples/aether-historical"
        paths = {role: root / f"{name}.{role}.json"
                 for role in ("export", "registry", "context")}
        pin = (root / f"{name}.context.sha256").read_text().strip()
        capture = invoke(name, paths, pin, 0)
        native = json.loads((root / f"{name}.report.json").read_text())
        assert capture["provider_report"] == native
        assert capture["invocation"]["outcome"] == "CONFIRMED"
        assert capture["authority"]["source_build_binding"] == "UNKNOWN"
        assert capture["authority"]["general_claim_verdict"] == "NOT_ASSESSED"
        check = cli(["validate-capture", str(args.out / name), "--expect-receipt", capture["receipt_digest"]], 0)
        assert check["provider_execution_reproduced"] == "NOT_RUN"
        (args.out / f"{name}.receipt.sha256").write_text(capture["receipt_digest"] + "\n")
        retained[name] = capture
        for path in [*paths.values(), root / f"{name}.context.sha256", root / f"{name}.report.json"]:
            sources[path.relative_to(checkout).as_posix()] = sha(path)

    fixture = checkout / "examples/aether-historical"
    paths = {role: fixture / f"retired-view.{role}.json" for role in ("export", "registry", "context")}
    original_pin = (fixture / "retired-view.context.sha256").read_text().strip()
    controls = []
    invoke("wrong-binary", paths, original_pin, 2, selected_binary="0" * 64)
    assert not (args.out / "wrong-binary").exists()
    controls.append("binary substitution rejected before invocation")
    invoke("wrong-context", paths, "0" * 64, 2)
    assert not (args.out / "wrong-context").exists()
    controls.append("external context substitution rejected before invocation")

    changed_root = args.out / "negative-inputs"
    changed_root.mkdir()
    changed = {role: json.loads(path.read_text()) for role, path in paths.items()}
    changed_paths = {role: changed_root / f"{role}.json" for role in paths}
    changed["registry"]["keys"][0]["status"] = "revoked"
    for fresh, name in ((False, "registry-replaced"), (True, "revoked-signer")):
        if fresh:
            changed["context"]["registry_digest"] = omega_digest("aether/historical-registry/v1", changed["registry"])
        for role, value in changed.items():
            write(changed_paths[role], value)
        pin = omega_digest("aether/historical-context/v1", changed["context"])
        report = invoke(name, changed_paths, pin, 2)
        assert report["invocation"]["outcome"] == "REJECTED"
        assert report["provider_report"]["status"] == "REJECTED"
        checked = cli(["validate-capture", str(args.out / name), "--expect-receipt", report["receipt_digest"]], 0)
        assert checked["provider_outcome"] == "REJECTED"
        controls.append(name + " retained as native REJECTED")

    good = retained["replay"]
    root = args.out / "replay"
    stdout = (root / "provider.stdout").read_bytes()
    (root / "provider.stdout").write_bytes(stdout + b" ")
    cli(["validate-capture", str(root), "--expect-receipt", good["receipt_digest"]], 2)
    (root / "provider.stdout").write_bytes(stdout)
    controls.append("captured stream modification rejected")
    altered = copy.deepcopy(good)
    altered["authority"]["source_build_binding"] = "CONFIRMED"
    altered["receipt_digest"] = receipt_digest(altered)
    original_receipt = (root / "receipt.json").read_bytes()
    write(root / "receipt.json", altered)
    cli(["validate-capture", str(root), "--expect-receipt", good["receipt_digest"]], 2)
    controls.append("whole capture rehash rejected under original receipt pin")
    cli(["validate-capture", str(root), "--expect-receipt", altered["receipt_digest"]], 2)
    controls.append("authority promotion rejected even under fresh receipt pin")
    (root / "receipt.json").write_bytes(original_receipt)

    constellation = {"repositories": [{"name": "CHIMERA-OMEGA", "role": "evidence-kernel",
                                       "url": "https://github.com/aixaria0/CHIMERA-OMEGA",
                                       "checkout": checkout.name}]}
    federation = federation_report(checkout.parent, constellation,
                                   load_catalog(PROJECT / "capabilities/catalog.json"))
    assert federation["valid"], federation
    write(args.out / "omega-federation.json", federation)
    source_files = ("chimera_one/offline_review.py", "chimera_one/cli.py", "capabilities/catalog.json",
                    "adapters/catalog.json", "tools/offline-omega-conformance.py")
    own_head = subprocess.check_output(["git", "-C", str(PROJECT), "rev-parse", "HEAD"], text=True).strip()
    write(args.out / "provenance.json", {
        "schema": "chimera-one-offline-conformance/v1", "one_checkout_revision": own_head,
        "one_working_tree_dirty": bool(subprocess.check_output(["git", "-C", str(PROJECT), "status", "--porcelain"], text=True)),
        "one_source_sha256": {p: sha(PROJECT / p) for p in source_files},
        "omega_source_repository": "aixaria0/CHIMERA-OMEGA", "omega_source_revision": OMEGA_REVISION,
        "omega_binary_sha256": binary_pin,
        "binary_pin_acquisition": "Local/CI build hash; production requires independently reviewed binary selection.",
        "source_fixture_sha256": sources, "positive_cases": ["replay", "retired-view"],
        "synthetic_fixture": "retired-view models an unsigned current-key assessment; no live rotation is claimed.",
        "rejection_controls": controls, "target_runtime_reproduction": "NOT_RUN",
        "public_testnet_interaction": "NONE", "source_build_attestation": "UNKNOWN",
        "artifact_sha256": {p.relative_to(args.out).as_posix(): sha(p) for p in sorted(args.out.rglob("*")) if p.is_file()},
    })
    print(json.dumps({"status": "CONFORMANCE_PASSED", "positive_cases": 2,
                      "rejection_controls": len(controls), "omega_federation": "VALID",
                      "target_runtime_reproduction": "NOT_RUN", "public_testnet_interaction": "NONE"}))


if __name__ == "__main__":
    main()
