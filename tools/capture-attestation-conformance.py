#!/usr/bin/env python3
"""Sign retained capture bytes with a public TEST vector; never invoke OMEGA."""
from __future__ import annotations

import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from chimera_one import capture_attestation as att
from chimera_one import offline_review as review

RECEIPT_PIN = "sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2"
KEY_PIN = "sha256:21fe31dfa154a261626bf854046fd2271b7bed4b6abe45aa58877ef47f9721b9"
SIGNER = "test-vector-reviewer"
# Published RFC 8032 vector: this seed is public and grants NO production authority.
TEST_SEED = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
FILES = ("inputs/export.json", "inputs/registry.json", "inputs/context.json",
         "provider.stdout", "provider.stderr", "receipt.json")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    original = PROJECT / "examples/offline-review/replay"
    before = {name: review._bounded_read(original / name) for name in FILES}
    controls = []
    output = args.out / "test-only.replay.attestation.json"
    with tempfile.TemporaryDirectory(prefix="one-owned-signature-conformance-") as temporary:
        stage = Path(temporary)
        root = stage / "capture"
        shutil.copytree(original, root)
        key = stage / "PUBLIC-TEST-VECTOR-ONLY.pem"
        der = bytes.fromhex("302e020100300506032b657004220420" + TEST_SEED)
        key.write_bytes(b"-----BEGIN PRIVATE KEY-----\n" + base64.b64encode(der)
                        + b"\n-----END PRIVATE KEY-----\n")
        key.chmod(0o600)
        authored = att.attest_capture(root=root, expected_receipt=RECEIPT_PIN, private_key=key,
                                     signer_id=SIGNER, expected_key=KEY_PIN, output=output)
        exact = review._bounded_read(output)
        expected_fixture = PROJECT / "examples/capture-attestation/test-only.replay.attestation.json"
        if expected_fixture.exists():
            assert exact == review._bounded_read(expected_fixture), "signed fixture drift"

        def verify(**overrides):
            arguments = dict(root=root, attestation=output, expected_receipt=RECEIPT_PIN,
                             expected_key=KEY_PIN, expected_signer=SIGNER)
            arguments.update(overrides)
            return att.verify_capture_attestation(**arguments)

        def reject(name, **overrides):
            try:
                verify(**overrides)
            except review.ReviewError:
                controls.append(name)
            else:
                raise AssertionError("accepted signature/capture substitution: " + name)

        report = verify()
        reject("unselected key", expected_key="sha256:" + "0" * 64)
        reject("unselected receipt", expected_receipt="sha256:" + "0" * 64)
        reject("unselected signer label", expected_signer="other-reviewer")
        original_attestation = json.loads(exact)
        changed = copy.deepcopy(original_attestation)
        changed["signature"] = "0" * 128
        changed["attestation_digest"] = att.attestation_digest(changed)
        write(output, changed)
        reject("invalid signature under fresh attestation hash")
        changed = copy.deepcopy(original_attestation)
        changed["statement"]["role"] = "EXECUTION_WITNESS"
        changed["attestation_digest"] = att.attestation_digest(changed)
        write(output, changed)
        reject("witness role substitution")
        changed = copy.deepcopy(original_attestation)
        changed["statement"]["source_build_binding"] = "CONFIRMED"
        changed["attestation_digest"] = att.attestation_digest(changed)
        write(output, changed)
        reject("signed authority extension")
        output.write_bytes(exact)
        (root / "provider.stdout").write_bytes(before["provider.stdout"] + b" ")
        reject("saved native output modification")
        (root / "provider.stdout").write_bytes(before["provider.stdout"])
        receipt = json.loads(before["receipt.json"])
        receipt["invocation_id"] = "00000000-0000-0000-0000-000000000001"
        receipt["receipt_digest"] = review.receipt_digest(receipt)
        write(root / "receipt.json", receipt)
        review.validate_capture(root, receipt["receipt_digest"])
        reject("valid signed receipt transplanted onto another occurrence",
               expected_receipt=receipt["receipt_digest"])
        receipt = json.loads(before["receipt.json"])
        receipt["authority"]["source_build_binding"] = "CONFIRMED"
        receipt["receipt_digest"] = review.receipt_digest(receipt)
        write(root / "receipt.json", receipt)
        reject("source-build promotion under fresh receipt pin", expected_receipt=receipt["receipt_digest"])
        (root / "receipt.json").write_bytes(before["receipt.json"])
        assert verify() == report
        assert before == {name: review._bounded_read(root / name) for name in FILES}
    assert before == {name: review._bounded_read(original / name) for name in FILES}
    assert authored["status"] == "SIGNED_NOT_AUTHORIZED"
    assert report["signature_integrity"] == "CONFIRMED"
    assert report["source_build_binding"] == "UNKNOWN"
    assert report["independent_observation"] == "UNKNOWN"
    assert report["provider_execution_reproduced"] == "NOT_RUN"
    write(args.out / "binding-report.json", report)
    write(args.out / "provenance.json", {
        "schema": "chimera-one-capture-attestation-conformance/v1",
        "mode": "PUBLIC_TEST_KEY_AND_RETAINED_REAL_CAPTURE_ONLY",
        "key_authority": "PUBLIC_RFC8032_TEST_VECTOR_ONLY",
        "expected_receipt": RECEIPT_PIN, "expected_key": KEY_PIN, "expected_signer": SIGNER,
        "attestation_digest": authored["attestation_digest"], "rejection_controls": controls,
        "fresh_provider_invocation": "NOT_RUN", "private_provider_checkout": "NOT_PERFORMED",
        "independent_witness": "NOT_ESTABLISHED", "source_build_binding": "UNKNOWN",
        "public_testnet_interaction": "NONE", "production_signer_enrollment": "NOT_PERFORMED",
        "control_plane_source_binding": "DISK_SOURCE_BYTES_ONLY",
        "control_plane_source_sha256": {name: review.sha256((PROJECT / name).read_bytes()) for name in
            ("chimera_one/capture_attestation.py", "chimera_one/offline_review.py", "chimera_one/protocol.py",
             "chimera_one/cli.py", "tools/capture-attestation-conformance.py")},
        "artifact_sha256": {p.name: review.sha256(p.read_bytes()) for p in sorted(args.out.iterdir()) if p.is_file()},
    })
    print(json.dumps({"status": "CONFORMANCE_PASSED", "rejection_controls": len(controls),
                      "key_authority": "PUBLIC_TEST_VECTOR_ONLY", "fresh_provider_invocation": "NOT_RUN"}))


if __name__ == "__main__":
    main()
