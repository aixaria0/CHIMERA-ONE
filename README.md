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
- pin an exact constellation baseline for reproducibility.

## Commands

```sh
python -m chimera_one capabilities
python -m chimera_one status --workspace ..
python -m chimera_one index --workspace ..
python -m chimera_one query evidence
python -m chimera_one plan "analyze this system change"
python -m chimera_one plan "falsify this staking claim" --domain rchain-audit
```

The planner does not execute its plan yet. That separation is intentional: adapters must prove their trust and evidence contracts before orchestration is allowed to invoke them.

## Architecture

Objective -> Planner -> Capability Registry -> RitualGraph policy/invariants -> Chimera-AG routing -> Aether execution -> observations -> RCHAIN-COMPLIER assurance -> OMEGA evidence binding -> synthesis with provenance.

See `docs/ARCHITECTURE.md`, `docs/KNOWLEDGE_FABRIC.md`, and the pinned baseline in `docs/BASELINE-2026-10-05.json`.
