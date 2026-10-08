# CHIMERA-ONE

CHIMERA-ONE is the sovereign intelligence control plane for the Chimera repository constellation.

It does not copy or absorb component implementations. It composes versioned capabilities while preserving each repository's trust and evidence boundary.

## Constellation

- RitualGraph — executable threat/state graphs and invariants
- Chimera-AG — measured specialist routing, councils, synthesis, verification
- aether-runtime — bounded allowlisted execution plane
- RCHAIN-COMPLIER — task-bound deterministic assurance and independent verifier receipts
- CHIMERA-OMEGA — proof-carrying evidence kernel and replay/binding
- chimera-rchain-staking-audit — adversarial RChain domain pack and first-divergence methodology

## Governing rule

Intelligence may propose. Execution must be bounded. Claims require evidence. Evidence does not silently become truth.

## What works now

`CHIMERA-ONE` can:

- validate a canonical cross-repository capability catalog;
- snapshot repository identity, branch, revision, cleanliness and origin binding;
- create a content-addressed local knowledge index without republishing private source;
- search that local index while preserving repository/path/digest provenance;
- compile an objective into a bounded multi-repository execution DAG;
- pin an exact constellation baseline for reproducibility;
- validate protocol runs through both Python and a deterministic Rust kernel;
- build a hardened multi-arch container carrying both control-plane and protocol-verifier surfaces.
- invoke one pinned offline OMEGA historical verifier and preserve its exact input snapshots, native report and bounded process result in an externally verifiable capture.
- sign a saved capture with a separately selected Ed25519 key and verify its signature and saved bytes under explicit receipt, key and signer-label pins.
- execute one pinned local Chimera-AG Council measurement against a matched four-call baseline, preserve raw native transcripts, and recompute reference scores without fresh inference.
- derive and validate one family-limited checked-program routing policy from two externally pinned native suites, without fresh inference.

## Commands

```sh
python -m chimera_one capabilities
python -m chimera_one federation --workspace ..
python -m chimera_one doctor --workspace ..
python -m chimera_one status --workspace ..
python -m chimera_one index --workspace ..
python -m chimera_one query evidence
python -m chimera_one plan "analyze this system change"
python -m chimera_one plan "falsify this staking claim" --domain rchain-audit
python -m chimera_one protocol-validate tests/vectors/run.valid.json
python -m chimera_one derive-program-policy \
  --evidence examples/program-routing/v3/evidence.json \
  --native-dir examples/program-routing/v3/native \
  --expect-evidence sha256:a010084f89462aadd7b8e4c9e498fe54264ee69cbd77dfa70b1a78ddbcc393b9
chimera-protocol validate-run tests/vectors/run.valid.json
```

The planner does not execute its plan yet. That separation is intentional: adapters must prove their trust and evidence contracts before orchestration is allowed to invoke them. The Rust protocol kernel validates and digests plans; it is not an unrestricted executor.

`review-aether-history` is the first narrow invocation adapter. It selects the
personally owned OMEGA source and explicit binary/context pins, constructs one
fixed offline command, and records success, rejection or blocked execution without
promoting general claims. `validate-capture` later checks saved bytes under an
external receipt pin without rerunning the provider. See the exact commands,
capture grammar and trust/resource limits in
[Offline OMEGA review](docs/OFFLINE_OMEGA_REVIEW.md).

`attest-capture` adds an Ed25519 sidecar without changing that capture.
`verify-capture-attestation` checks its signature and all saved bytes with explicit
receipt/key/label selections. It requires OpenSSL 3 and preserves unknown witness
independence and source-build binding. Reproducible commands and a public test-key
fixture are in [Capture attribution](docs/CAPTURE_ATTESTATION_V1.md).

`bind-capture-build` joins a saved capture to separately pinned OMEGA build
artifacts through the fixed external offline checker. `validate-capture-build`
checks only the pinned saved link/capture bytes; `reverify-capture-build` repeats
the external saved source/tree/binary checks. The original receipt remains
unchanged, build execution stays attributed, and neither mode promotes claim
truth or witness independence. Commands, literal native fixture pins and the
two verification scopes are in [Capture build link](docs/CAPTURE_BUILD_LINK_V1.md).

`measure-chimera-council` adds a bounded local-model experiment with explicit
source, suite and model selections. `validate-council-capture` checks its saved
bytes and invokes only the pinned external transcript checker. The retained
negative comparison, zero-call dry run, exact commands and execution limits are
in [Council measurement](docs/COUNCIL_MEASUREMENT_V1.md). This adapter runs
separately from the general planner and does not promote model agreement.

`derive-program-policy` verifies the retained V3 native suite/report bytes,
consumes their reviewed compact evidence and selects
four checked single-model samples for the three exact typed task families. Across
the regression and transfer suites this route delivered 24/24 answers versus
23/24 for Council, with zero false accepts and lower observed elapsed time on
both suites. `validate-program-policy` recomputes the decision under external
evidence/policy pins with no inference. The policy does not apply outside those
families or authorize general-plan execution. See
[Checked-program routing policy](docs/PROGRAM_ROUTING_POLICY_V1.md).

The central catalog includes all six current OMEGA capabilities. Registration
does not authorize automatic execution of other catalog commands. Engineering
stays within personally owned repositories; public testnets and third-party
operational targets are off-limits under [AGENTS.md](AGENTS.md).

## Build surfaces

```sh
make test
make conformance
docker compose run --rm control-plane
docker compose run --rm protocol-check
CHIMERA_WORKSPACE=.. docker compose --profile workspace run --rm federation
```

GitHub Actions separately gate Python/Rust conformance, Rust supply-chain audits, multi-architecture container builds, release packaging, and optional live six-repository federation checks. See `docs/BUILD_AND_SUPPLY_CHAIN.md`.

## Architecture

Objective -> Planner -> Capability Registry -> RitualGraph policy/invariants -> Chimera-AG routing -> Aether execution -> observations -> RCHAIN-COMPLIER assurance -> OMEGA evidence binding -> synthesis with provenance.

See `docs/ARCHITECTURE.md`, `docs/KNOWLEDGE_FABRIC.md`, and the pinned baseline in `docs/BASELINE-2026-10-05.json`.
