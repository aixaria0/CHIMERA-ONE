# One offline OMEGA invocation with a portable capture

`review-aether-history` is ONE's first narrowly bounded executable adapter. It
calls the existing OMEGA historical receipt/journal verifier and preserves exact
input snapshots, stdout/stderr, exit status and the complete attributed native
report in a new bundle. The general planner still emits `PLANNED` steps and
`HYPOTHESIS` claims. This adapter does not execute that plan or other catalog
commands, route LLMs or contact operational targets.

## Pinned contract

| Selection | Required value or rule |
| --- | --- |
| Provider | Personally owned `aixaria0/CHIMERA-OMEGA` |
| Git revision | `52a21a8eaa4363d648fdac805900175d81e13f07` |
| Git tree | `ddb6a6b8ee60ee0ac5b865a69a8a60bf0cf06c0e` |
| Manifest SHA-256 | `d5d1ec1e80249ba607dcffdd13d8e6baf4413b8277cbce64a71efe59decbfde3` |
| Capability | `omega.verify-aether-historical-journal` |
| Native report schema | `chimera-aether-historical-journal-binding/v1` |
| Native report scope | `EXACT_RECEIPT_REGISTRY_AUTHORIZATION_AND_PINNED_COMPLETE_JOURNAL_ONLY` |
| Binary | Required independently selected lowercase SHA-256; the exact copied bytes are checked and executed |
| Evidence | Required external OMEGA historical-context pin |
| Saved capture | Required external `sha256:` receipt digest when validating saved bytes |

The checkout must be clean, at the exact revision/tree, and bound to the personal
GitHub origin, using HTTPS or its equivalent SSH form. The adapter performs no
fetch, clone or checkout. Manifest bytes must match the supported source pin and
declare verification, network `none` and mutation `none`. ONE constructs one fixed
argument list without a shell; it never executes the manifest's command. Catalog
registration gives other commands no automatic execution authority.

Source identity, binary identity and execution attestation remain separate. A
clean Git checkout does not prove a binary was built from it. ONE records the
binary SHA-256 and local control-plane source hashes as `DISK_SOURCE_BYTES_ONLY`;
`source_build_binding` remains `UNKNOWN`. Computing a hash from an untrusted binary
at execution time does not select trusted authority. CI's local-build hash is a
conformance acquisition, not a production trust channel.

## Process and filesystem boundaries

Each input is a regular local file of at most 1 MiB. JSON requires unique ASCII
keys, depth at most 32, safe unsigned integers and strings at most 4096 UTF-8 bytes.
The binary is at most 64 MiB. POSIX invocation has a ten-second timeout, no stdin,
a fixed minimal environment and at most 128 KiB each of stdout and stderr. Only
the invocation's owned process group is stopped.

ONE copies inputs into private temporary state rather than handing originals to
the provider. Changed/deleted snapshots block the invocation. The final bundle
seals fresh original bytes, raw output and the receipt after the provider stops.
The output directory must be new and outside the provider checkout, including
through symlinked parents. Existing bundles are not overwritten. Copying evidence
bytes does not copy timestamps, filesystem metadata or xattrs, which have no
authority here and are not portable across UserLAnd.

This is a process/resource and capture boundary, not an OS sandbox. The reviewed
OMEGA command performs no network I/O; ONE cannot prove an arbitrary selected
executable lacks filesystem/network access. `os_network_sandbox` is
`NOT_ESTABLISHED`. Review the binary pin before invocation. Public/shared testnets
and third-party operational targets remain off-limits under [AGENTS.md](../AGENTS.md).

## Capture grammar and authority

Every invocation gets a fresh UUID occurrence ID independent of content digests.
Two invocations of identical inputs can therefore retain identical native report
bytes but different occurrence IDs and receipt digests. This does not prove
independent operators or observation.

`receipt.json` uses `chimera-offline-review/v1`. It records provider revision,
tree and manifest; binary and context pins; control-plane source declarations;
resource bounds; per-file SHA-256/byte counts; the fixed normalized command;
exit/outcome/reason and snapshot integrity; complete native report; and authority
dimensions. See [the JSON grammar](../contracts/offline-review.schema.json).
The receipt digest is SHA-256 of
`chimera-offline-review/v1\0 || canonical_JSON(receipt_without_receipt_digest)`,
prefixed with `sha256:`. OMEGA context domains and ONE's existing protocol digest
are distinct and remain unchanged.

| File | Preserved evidence |
| --- | --- |
| `inputs/export.json` | Exact saved complete journal export bytes |
| `inputs/registry.json` | Exact selected key/policy registry bytes |
| `inputs/context.json` | Exact selected historical context bytes |
| `provider.stdout` | Exact bounded native stdout |
| `provider.stderr` | Exact bounded native diagnostics |
| `receipt.json` | Content-addressed invocation occurrence and attributed report |

| CLI exit | Meaning |
| --- | --- |
| Review 0 | Native exit 0 with a supported scoped `CONFIRMED` report captured |
| Review 2 | Preflight rejected, or native exit 2 with its `REJECTED` report captured |
| Review 3 | Invocation captured as `BLOCKED`: timeout, overflow, signal/unexpected exit, input mutation, malformed report or authority drift |
| Capture validation 0 | Saved bytes match the externally pinned receipt and contract, including a recorded `REJECTED` or `BLOCKED` provider outcome |
| Capture validation 2 | Pin, file bytes, structure, scope or contextual bindings rejected |

The native report is stored unchanged. Successful reports must bind the captured
export, registry and certificate digests to their context, match selected
head/count and preserve the receipt/journal predicates, direct-parent boundary,
attributed producer view and UNKNOWN/NOT_RUN dimensions. This is report/input
binding; ONE does not reimplement Ed25519 or journal verification.

`validate-capture` rereads bounded saved bytes, checks receipt/file digests and
the fixed invocation/report contract, and rejects authority promotion even under
a newly selected receipt pin. It starts no provider. Its scope is
`RECORDED_BYTES_MATCH_EXTERNALLY_PINNED_RECEIPT_ONLY`: provider execution is
`NOT_RUN`, independent observation stays `UNKNOWN`, general claim verdict is
`NOT_ASSESSED`. Captures are content-addressed records, not signatures or an
append-only external log. Obtain the receipt pin through a trusted review path;
reading it from an untrusted bundle cannot authorize that bundle.

Neither hashing nor a scoped native `CONFIRMED` report establishes global truth,
finality, freshness, organizational independence or target runtime reproduction.

## Reproduce a reviewed saved fixture

1. Preserve the original personal OMEGA checkout and make an isolated checkout at
   the supported revision. Build its offline verifier:

   ~~~sh
   git -C /path/to/your/CHIMERA-OMEGA worktree add --detach \
     /path/to/omega-reviewed 52a21a8eaa4363d648fdac805900175d81e13f07
   cargo build --locked --manifest-path /path/to/omega-reviewed/Cargo.toml --bin omega
   ~~~

2. Review the export, registry, context and binary through your trusted process.
   From ONE's source directory, run with your independently selected pins:

   ~~~sh
   python3 -m chimera_one review-aether-history \
     --omega-checkout /path/to/omega-reviewed \
     --omega-bin /path/to/omega-reviewed/target/debug/omega \
     --expect-omega-binary "$REVIEWED_OMEGA_BINARY_SHA256" \
     --export /path/to/omega-reviewed/examples/aether-historical/replay.export.json \
     --registry /path/to/omega-reviewed/examples/aether-historical/replay.registry.json \
     --context /path/to/omega-reviewed/examples/aether-historical/replay.context.json \
     --expect-context "$REVIEWED_HISTORICAL_CONTEXT_SHA256" \
     --output /path/to/new-review-bundle
   ~~~

   The retained replay fixture's context pin is
   `f7ccfdb318101446e01ea15407b844491cb8e08bcd5aeed7ead747b6e7cf3ca6`.
   It selects this fixture only, not production or other evidence.

3. Retain the returned receipt pin through your review channel, then check saved
   bytes later without starting OMEGA:

   ~~~sh
   python3 -m chimera_one validate-capture /path/to/new-review-bundle \
     --expect-receipt "$REVIEWED_CAPTURE_RECEIPT_DIGEST"
   ~~~

## Real-provider conformance

~~~sh
python3 -m unittest discover -s tests -v
python3 tools/offline-omega-conformance.py \
  --omega-checkout /path/to/omega-reviewed \
  --omega-bin /path/to/omega-reviewed/target/debug/omega \
  --out /path/to/new-conformance-output
~~~

The harness invokes real OMEGA on saved replay and synthetic retired-view fixtures,
compares complete reports against their golden reports, checks unchanged originals
and seven rejection controls, and validates OMEGA's current manifest against the
updated central catalog. Retired-view models an unsigned current-key assessment;
no live key rotation or new target acquisition is claimed. Failed native reviews
remain `REJECTED` captures.

Unit tests use explicitly test-only provider doubles for timeout, overflow,
snapshot mutation, wrong pins, scope/authority drift and capture substitution.
These are boundary controls, not claims that real OMEGA exhibited those behaviors.
OMEGA is a private personal repository. The default ONE Actions token cannot
check it out. CI therefore runs `tools/recorded-capture-conformance.py` against
the retained real capture, checks five substitution controls, and preserves
`one-offline-omega-evidence`. That lane declares `RETAINED_CAPTURE_BYTES_ONLY`,
fresh provider invocation `NOT_RUN` and private source checkout `NOT_PERFORMED`.
No additional credentials or repository visibility changes are introduced.
The real-provider harness above remains runnable on an authorized local checkout;
its successful two-case/seven-control arm64 acquisition is retained separately.
Other capabilities remain metadata until their own adapter is implemented.

The capture can also carry a separate Ed25519 attestation under independently
selected receipt, key and signer-label pins. See
[capture attribution](CAPTURE_ATTESTATION_V1.md). The original receipt and native
report are preserved; signing does not establish an independent witness,
source-to-binary build binding, freshness or general claim truth.

An exact retained replay capture is checked in under `examples/offline-review`,
with acquisition/source/binary/artifact hashes and the explicit dirty-worktree
declaration from pre-commit conformance. Its source-byte hashes identify the tested
implementation without pretending the acquisition already had a published commit.
Validate it without installing or invoking OMEGA:

~~~sh
python3 -m chimera_one validate-capture examples/offline-review/replay \
  --expect-receipt sha256:ad8ca4df8e73093232f1cd7302ed255287d9383a56e8ad55e52a768e7491d5a2
~~~
