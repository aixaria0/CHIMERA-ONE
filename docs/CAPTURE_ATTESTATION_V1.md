# Offline Ed25519 capture attribution

ONE can sign an existing `chimera-offline-review/v1` capture and verify the
signature together with the saved input/output bytes. The new attestation is a
separate file. The original receipt, its digest, raw inputs, native report and
recorded provider outcome remain unchanged.

This slice closes the missing cryptographic attribution of a saved capture. An
independent witness and a source-to-binary build proof still require separate
evidence. No production signer is enrolled by this change.

## Selections and meaning

Every command requires an independently selected receipt digest and signer key
fingerprint. Verification also requires the selected signer label. No value is
silently adopted from the attestation as trusted authority.

| Value | Meaning |
| --- | --- |
| `--expect-receipt` | Existing externally selected `sha256:` receipt digest |
| `--expect-key` | `sha256:` fingerprint of the **raw 32-byte** Ed25519 public key |
| `--signer-id` / `--expect-signer` | Signed caller-selected label, `[a-z][a-z0-9._-]{0,63}` |
| Role | Fixed `CAPTURE_REVIEWER`; never an execution or independence witness |
| Authoring status | `SIGNED_NOT_AUTHORIZED` |
| Verification scope | `PINNED_KEY_SIGNATURE_AND_SAVED_CAPTURE_BYTES_ONLY` |

The receipt digest already binds the provider source/tree/manifest, binary and
context selections, all saved artifacts, exact native report and authority
dimensions. The signed statement additionally binds its occurrence UUID, signer
label, public key, key fingerprint, fixed role and exact scope. There is no
timestamp, challenge or new occurrence: signing the same capture with the same
key and label produces identical signatures. Replay establishes no freshness.

The label-to-key mapping is caller-selected attribution, not a real-world identity
proof or policy registry. Key possession does not authorize an operator. Signature
verification does not rerun OMEGA or establish that the originally captured
provider result is true. A valid `REJECTED` or `BLOCKED` capture can be signed and
verified while retaining that outcome.

| Report predicate | Successful result |
| --- | --- |
| Signature / selected key / selected label binding | `CONFIRMED` |
| Saved capture validation | Original scoped validation report and provider outcome |
| Policy authorization / general claim verdict | `NOT_ASSESSED` |
| Signer identity / independent observation / process independence | `UNKNOWN` |
| Source-build binding / freshness / revocation | `UNKNOWN` |
| Provider execution reproduced | `NOT_RUN` |

## Host and key requirements

Use Python 3.11+ on POSIX with the host's trusted OpenSSL 3 installation. Python
package dependencies remain empty and the Rust lock graph is unchanged. The
Docker image and UserLAnd bootstrap explicitly include OpenSSL. Python and
OpenSSL are part of the verifier's local trust base, not dynamically selected
capability commands. This is not an OS sandbox or a remote-attestation system.

Provision and review a key outside this tool. The signer accepts an unencrypted
Ed25519 PEM private key in a regular, owner-only file outside the capture. Group
or world permissions, special files, oversized keys, other key algorithms and
native crypto failures are rejected. Encrypted keys, interactive passphrases,
HSMs, key generation, rotation, recovery and revocation services are not provided.

The secret is copied into an owned temporary directory, mode 0700, with a mode
0600 key file. Native commands receive file paths, not secret bytes in argv.
Diagnostics are suppressed. Temporary files are removed when the command ends;
there is no secure disk-erasure or memory-zeroization guarantee. Capture files
and production secrets are not modified or retained in conformance artifacts.

The attestation is at most 8 KiB and the key at most 8 KiB. The existing bounded
JSON rules apply. Fixed native operations use the existing ten-second / 128 KiB
per-stream process primitive, no shell, no stdin and a minimal environment. Each
operation runs in its owned process group. Inputs are copied into private bounded
state and fully validated before signing or signature verification. A new output
file must be outside the original capture, including through symlinked parents;
existing outputs are never overwritten.

## Author and verify a reviewed capture

1. Select the saved capture's receipt digest, reviewer's raw-public-key SHA-256
   fingerprint and signer label through your trusted review path. Set
   `REVIEWED_CAPTURE_RECEIPT_DIGEST`, `REVIEWED_SIGNER_KEY_ID` and
   `REVIEWED_SIGNER_LABEL` from those selections. Keep the private key outside
   repositories and evidence bundles, with owner-only permissions.

2. Sign the existing capture with that explicit key:

   ~~~sh
   python3 -m chimera_one attest-capture /path/to/saved-capture \
     --expect-receipt "$REVIEWED_CAPTURE_RECEIPT_DIGEST" \
     --expect-key "$REVIEWED_SIGNER_KEY_ID" \
     --signer-id "$REVIEWED_SIGNER_LABEL" \
     --key /path/to/private/reviewer.pem \
     --output /path/to/new-sidecar.attestation.json
   ~~~

3. Verify later without the secret, provider source or provider binary:

   ~~~sh
   python3 -m chimera_one verify-capture-attestation /path/to/saved-capture \
     --expect-receipt "$REVIEWED_CAPTURE_RECEIPT_DIGEST" \
     --expect-key "$REVIEWED_SIGNER_KEY_ID" \
     --expect-signer "$REVIEWED_SIGNER_LABEL" \
     --attestation /path/to/new-sidecar.attestation.json
   ~~~

Both commands return exit 0 for their scoped success or exit 2 with a structured
`REJECTED` result. Missing required CLI selections are usage errors.

## Reproduce the public test-key fixture

The checked-in sidecar signs a previously retained real OMEGA capture with a
**public RFC 8032 test key**. Everyone knows that test seed; it grants no production
authority, independent witness status or fresh provider acquisition. No private
provider checkout or credentials are needed.

~~~sh
python3 -m chimera_one verify-capture-attestation examples/offline-review/replay \
  --expect-receipt sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2 \
  --expect-key sha256:21fe31dfa154a261626bf854046fd2271b7bed4b6abe45aa58877ef47f9721b9 \
  --expect-signer test-vector-reviewer \
  --attestation examples/capture-attestation/test-only.replay.attestation.json

python3 -m unittest discover -s tests -v
python3 tools/capture-attestation-conformance.py --out /path/to/new-evidence-output
~~~

Conformance checks the deterministic fixture and nine substitution controls. It
retains only the public attestation, binding report and explicit provenance; the
temporary public-test-key PEM is removed. Unit tests also check the RFC 8032
one-byte reference signature, separate CLI processes, rejected/blocked captures,
JSON ambiguity, crypto failure, key-file constraints and preserved outputs.

## Encoding

See [the strict JSON grammar](../contracts/capture-attestation.schema.json).
Statements use ONE canonical JSON: sorted ASCII keys, compact separators, UTF-8,
no floating-point values. Ed25519 signs the exact bytes:

~~~text
CHIMERA-ONE\0capture/ed25519-statement/v1\0 || canonical_JSON(statement)
~~~

The complete attestation excluding its own digest is hashed as:

~~~text
sha256:SHA256(CHIMERA-ONE\0capture/attestation/v1\0 || canonical_JSON(body))
~~~

OpenSSL performs standard Ed25519 operations using `pkeyutl -rawin`. Public keys
use RFC 8410 SubjectPublicKeyInfo with absent algorithm parameters. References:
[OpenSSL 3 pkeyutl](https://docs.openssl.org/3.0/man1/openssl-pkeyutl/),
[RFC 8410](https://www.rfc-editor.org/rfc/rfc8410.html),
[RFC 8032 test vectors](https://www.rfc-editor.org/rfc/rfc8032.html#section-7.1).
