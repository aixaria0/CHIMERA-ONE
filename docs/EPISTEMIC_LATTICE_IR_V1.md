# Epistemic Lattice IR v1

`lattice-ir` is a bounded epistemic intermediate representation for CHIMERA-ONE. It does **not** decide external truth. It makes evidence promotions explicit, replayable, and rejectable.

## Why a product lattice

A single scalar status loses information. A signed artifact with no replay and an unsigned replayed artifact are not ordered by a meaningful universal verification level. v1 therefore models ten independently promoted dimensions: observation, integrity, reproduction, provenance, authorization, independence, freshness, adversarial coverage, formal proof, and implementation binding.

Vectors are compared component-wise. If each is stronger on a different dimension, the result is `INCOMPARABLE`. A vote, signature, replay, or formal proof in one dimension cannot silently promote another.

## Non-promotion kernel

Every increase is an `EvidenceEdge`. It must start at the exact current value, strictly increase one dimension, carry a content-addressed witness, and use a witness class authorized for that dimension. Strong targets including `SIGNED`, `REPLAY_VERIFIED`, `MODEL_CHECKED`, and `SEMANTICS_BOUND` have extra witness-kind gates.

A claim is valid only when replaying its evidence edges from the all-`UNKNOWN` vector reproduces its declared final vector. A final status cannot simply be inserted.

## OMEGA import boundary

The first importer accepts only `chimera-aether-lineage-binding/v1`. Confirmed signature integrity becomes `integrity=SIGNED`; the supported revision becomes `provenance=SOURCE_PINNED`; confirmed raw-operation, policy, and lineage bindings become `implementation_binding=SOURCE_PINNED`.

It deliberately leaves reproduction and independence `UNKNOWN` when OMEGA reports `NOT_RUN` / `UNKNOWN`, and it does not turn OMEGA `status=CONFIRMED` into external truth.

## Real Nexus semantic audit

The retained audit pins `aixaria0/nexus-quantum@d1cbd3623f3877c4f2f70b272ff107b81dc30be9` plus SHA-256 for the exact Lean and Python files.

The overclaim manifest checks runtime statements explicitly presented as Lean-derived. The source contains `zfa_implies_null_spectral` with a `c ≠ 0` conclusion, but it does not contain `NullCone_implies_Consistency`, `c ≤ 1`, or a `count ≤ 100` theorem. Those stronger runtime attributions therefore fail as `SEMANTIC_OVERPROMOTION`.

There is a second, independent reason not to promote this artifact to `MODEL_CHECKED`: the retained GitHub Actions run for this exact Nexus commit (`34379861313`) completed with `Machine-check QLF_NullCone` failing. The runnable example therefore records only `formal_proof=DECLARED`; `lattice next` recommends `ACQUIRE_MACHINE_CHECK`. A future successful, pinned machine-check must arrive as a different witness class before that coordinate may increase.

The companion `reclassified.json` classifies the unsupported numeric upper bounds as engineering/domain policy instead of formal theorem consequences. The same byte-pinned semantic audit then passes. Passing only means this overpromotion was removed; it does not prove the policy values correct and it does not promote the failed formal check.

## CLI

```bash
cargo run --locked -p lattice-ir --bin lattice -- validate claim.json
cargo run --locked -p lattice-ir --bin lattice -- compare vector-a.json vector-b.json
cargo run --locked -p lattice-ir --bin lattice -- next examples/lattice/nexus-gap.claim.json
cargo run --locked -p lattice-ir --bin lattice -- omega-import examples/omega/echo.report.json
cargo run --locked -p lattice-ir --bin lattice -- nexus-audit examples/nexus-proof-binding/overclaim.json /path/to/pinned/nexus
```

`nexus-audit` exits `4` when an audit completed and found semantic failures. Input, source-pin, or schema errors use `2` or report `REJECTED`.

## v1 boundary

The scheduler is intentionally rule-based and only recommends the next evidence action. It does not execute it. The Nexus checker is a bounded obligation checker over reviewed source patterns, not a general theorem-to-program equivalence prover. Those limits are part of the contract.
