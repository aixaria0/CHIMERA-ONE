# Capture/build evidence link v1

This adapter connects the selected binary digest in one externally pinned ONE
capture to two separately selected OMEGA build records. The compiled source stays
at `52a21a8eaa4363d648fdac805900175d81e13f07`, tree
`ddb6a6b8ee60ee0ac5b865a69a8a60bf0cf06c0e`; the offline Python build checker is
separately pinned at `9ab2390364fd8c89f29fa46569b58d33ddb61869`, tree
`d80c482dc2a6e20ba4e2cc56217b773772b61610`, SHA-256
`40346dd9adac3c22401cfd9a83a729c164d2951f2baf692bf74b4316f78caff1`.

`bind-capture-build` validates a private capture snapshot, snapshots the bounded
external build artifacts and executes only that selected checker's `compare`
command. OMEGA recomputes the saved source Git objects, commit, lock/manifest
bindings, records and native binary hashes. The resulting sidecar binds the exact
capture receipt and invocation UUID, source, binary, controller, records, builder
labels and raw checker transcript. It emits `RECORDED_NOT_AUTHORIZED`.

The original capture and any Ed25519 attestation are unchanged. Its v1 authority
continues to say `source_build_binding = UNKNOWN`; the separately selected sidecar
adds a scoped evidence link, not an implicit schema migration or a remote execution
attestation. A matching link is valid for rejected/blocked captures too, without
promoting their outcomes. It selects no signer or policy authority.

## Commands and distinct modes

1. Obtain and review the two raw OMEGA builder artifacts through your trusted
   path. Keep them outside ONE. Verify their archive digests and build evidence
   before executing a selected binary. The checker and source are distinct clean
   owned Git checkouts at the revisions above. No command here downloads them.
2. Create a fresh `review-aether-history` capture with that selected binary and
   externally selected historical context; see [the existing capture
   commands](OFFLINE_OMEGA_REVIEW.md). Select its new receipt digest through the
   review path. Old ARM64/debug capture bytes do not match this native build.
3. Author a new sidecar with all receipt/binary/controller/build pins supplied
   separately. Supply new owned output paths. The recorded native occurrence uses:

```sh
python3 -m chimera_one bind-capture-build /tmp/native-capture \
  --expect-receipt sha256:8832edd572eb04f9cab4f24c082628a66f429dc93ef0945e7cf7025f9ee1861d \
  --expect-omega-binary 3989b0b32395b21f1d33468e3af65225e36c22ea28fa7e931807bb8b02a54d10 \
  --expect-controller 40346dd9adac3c22401cfd9a83a729c164d2951f2baf692bf74b4316f78caff1 \
  --expect-left-record sha256:02249909a7fbd5e5007785b6f4ceb5621b6ad89a34c0f3d4669784e6b9ccad26 \
  --expect-right-record sha256:c050c79699b77eb86afc11c9642d164f4ec364c487dcc1841ab3e1ab6714649a \
  --left-builder builder-a --right-builder builder-b \
  --build-checkout /tmp/omega-build-checker \
  --left-build /tmp/omega-build-a --right-build /tmp/omega-build-b \
  --output /tmp/native-build-link.json
```

The receipt pin above belongs only to the recorded capture fixture. A fresh
invocation has a fresh UUID and different receipt/link pins. Copying values from
untrusted records provides no external selection. Binary/controller pins use raw
64-character lowercase SHA-256; receipt/link/build-record pins use `sha256:`.

4. `validate-capture-build` requires the saved capture, `--link`, `--expect-link`
   and all seven receipt/build/builder selections above. It takes no private
   checkout or build directories and runs no subprocess. It reports
   `SAVED_CAPTURE_AND_ATTRIBUTED_BUILD_REPORT_ONLY` with
   `raw_build_evidence_reverified = NOT_RUN`. The captured checker success is
   attributed evidence, not a current source/binary verification.
5. `reverify-capture-build` requires the same pins plus `--build-checkout`,
   `--left-build`, `--right-build`. It repeats OMEGA's full saved-byte verification
   and requires its raw transcript to match the pinned link. It reports
   `REVERIFIED_EXTERNAL_SAVED_SOURCE_AND_BINARY_BYTES` with
   `raw_build_evidence_reverified = CONFIRMED`. It does not compile or rerun OMEGA's
   native verifier. Missing raw evidence fails; it never falls back to saved mode.

Both verification commands exit 0 only for their stated binding scope and exit 2
for selection, grammar, I/O, resource, artifact or checker errors. They preserve
the original provider outcome separately from link validity.

## Contract and execution boundary

The sidecar schema is `chimera-capture-build-link/v1`. Its exact root fields are
`schema`, `status`, `scope`, `capture`, `build_selection`, `checker`,
`checker_invocation`, `comparison`, `authority`, `link_digest`. Extra fields,
authority extensions, duplicate JSON fields, floats and Boolean exit codes fail
closed. The [JSON schema](../contracts/capture-build-link.schema.json) describes
the structural contract; runtime checks also enforce external selection, distinct
records/builders and equality with the selected capture/report.

`link_digest` is `sha256:SHA256(CHIMERA-ONE\0capture/build-link/v1\0 ||
canonical_json(link_without_link_digest))`, using the existing ONE canonical JSON.
The private sidecar output is created exclusively with mode 0600. Outputs inside
the capture, checker or either original build directory are refused.

The checker's own repository/revision/tree/origin/cleanliness and exact script
bytes are checked before use. Only that script is copied to private temporary
state, then run with the trusted local Python interpreter's `-I -B` flags, closed
stdin, a minimal environment, fixed arguments, the existing 10-second timeout,
128-KiB stream bounds and an owned process group. Native OMEGA and Cargo are not
called by these three commands. Host Python and selected OMEGA checker correctness
remain trust assumptions; this adapter is not an OS sandbox.

Build directory membership is fixed: OMEGA's 14 files per builder, each at the
original source/binary/log byte bounds. Symlinks, special files, extra/missing
members and oversized files are refused before checker execution. Source archives
and native binaries are private temporary verification inputs; they are not
committed, vendored or imported into ONE. Original checkouts, builds and captures
are never modified.

## Recorded evidence and validation

[The small native fixture](../examples/capture-build/native-replay/) contains a
fresh real x86_64 OMEGA replay capture and the actual link/report bytes. The binary
is the 2,230,776-byte output from [OMEGA CI
37707542253](https://github.com/aixaria0/CHIMERA-OMEGA/actions/runs/37707542253), SHA-256
`3989b0b32395b21f1d33468e3af65225e36c22ea28fa7e931807bb8b02a54d10`. The new receipt is
`sha256:8832edd572eb04f9cab4f24c082628a66f429dc93ef0945e7cf7025f9ee1861d`, and the link is
`sha256:499bad56abc83a7da78928d6557a6429eacfdbc4e60cee634f33d58a8f103419`.

The acquisition ran the real ONE CLI against that native binary on saved owned
Aether replay evidence. Binding and full raw source/binary re-verification also
ran through the real CLI. There are 14 saved-link substitution controls and five
additional controls against the actual raw build artifacts: fully rehashed source,
binary, occurrence and tool-fingerprint substitution, plus raw-log corruption.
The boundary tests use explicitly named process doubles; the native fixture does
not. Tests and conformance preserve provider outcome and all authority limits.

ONE's normal CI runs 14 retained saved-byte controls without cross-repository
credentials; its container does the same saved-link validation as a non-root user
with read-only fixtures. These lanes do not claim to repeat the private raw build
check. To repeat the full offline harness with selected local artifacts:

```sh
python3 tools/capture-build-conformance.py --out /tmp/new-link-controls \
  --build-checkout /tmp/omega-build-checker \
  --left-build /tmp/omega-build-a --right-build /tmp/omega-build-b
```

Build execution remains `ATTRIBUTED_NOT_ATTESTED`; compiler correctness, complete
toolchain closure, independent observation, organizational/hardware independence
and freshness remain `UNKNOWN`. Signer authorization and general claims are
`NOT_ASSESSED`; target runtime reproduction is `NOT_RUN`. Full raw re-verification
authenticates selected artifact relationships under the reviewed checker trust
boundary, not a live process, compiler theorem or independent witness.
