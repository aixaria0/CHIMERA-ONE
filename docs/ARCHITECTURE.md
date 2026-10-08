# Architecture

CHIMERA-ONE is a federation control plane, not a monorepo merger.

## Trust ordering

AI proposal < observation < reproduced observation < independently checked evidence < pinned deterministic verification < formally justified property.

No council vote, confidence score, or model count may promote a claim above its evidence class.

## Component boundaries

| Component | Primary authority | Must not claim |
|---|---|---|
| Chimera-AG | measured routing and synthesis | factual truth from consensus alone |
| RitualGraph | typed threat transitions and invariants | arbitrary code execution |
| Aether | bounded allowlisted execution | proof from a success flag or digest |
| RCHAIN-COMPLIER | deterministic task-bound assurance | external provenance it did not observe |
| OMEGA | pinned evidence binding and replay | external truth or independence without evidence |
| RChain audit | adversarial domain evidence | generalized protocol safety |

## First golden path

1. Normalize an objective into a `chimera-run/v1` record.
2. Resolve only declared `chimera-capability/v1` capabilities.
3. Compile relevant safety/invariant policy through RitualGraph.
4. Select measured specialists through Chimera-AG.
5. Execute only an allowlisted operation through Aether.
6. Record raw observations and content digests.
7. Ask RCHAIN-COMPLIER to reproduce the bounded claim with independent local identities.
8. Bind/replay the evidence package with OMEGA.
9. Re-evaluate invariants.
10. Synthesize the answer while preserving epistemic status and provenance.

## First executable integration

The golden path above remains a plan. `review-aether-history` implements one
explicitly selected offline OMEGA invocation, separately from general plan
execution. It preserves original artifacts, exact native stdout/stderr, process
outcome, source/binary/context pins and an occurrence-specific capture receipt.
The provider result stays attributed; the general claim remains unassessed.
`validate-capture` checks saved bytes under an external receipt pin without
rerunning the provider. The [exact adapter contract](OFFLINE_OMEGA_REVIEW.md)
defines its authority and resource boundaries.

The updated registry recognizes all current OMEGA manifest capabilities.
Registration is descriptive and grants no automatic execution permission.

## Executable reasoning measurement

`measure-chimera-council` is a second fixed adapter: one personally owned,
source-pinned local-model experiment with matched four-call caps. It captures
raw native requests/responses and invokes the provider's separate deterministic
reference evaluator. `validate-council-capture` recomputes saved transcripts
without model inference. Candidates, model approvals, delivered answers and
reference matches remain distinct; a model vote does not establish truth.
The [adapter contract](COUNCIL_MEASUREMENT_V1.md) pins source and selected evidence,
preserves failure/UNKNOWN dimensions and leaves general plan execution unchanged.

## Narrow measured routing decision

`derive-program-policy` consumes two externally pinned Chimera-AG V3 program
summaries after their raw artifacts were independently replayed. For integer
expressions, bounded state transitions and directed reachability, it selects the
four-sample checked-program arm only when it is noninferior in verified delivery,
has zero false accepts and is faster on each selected suite. Any other metrics
produce `NO_SELECTION`. The decision remains separate from the general planner;
its [contract](PROGRAM_ROUTING_POLICY_V1.md) preserves source, artifact, suite,
report, evidence and policy pins and keeps AGI/generalization unassessed.
