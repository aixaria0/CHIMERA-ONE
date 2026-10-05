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
