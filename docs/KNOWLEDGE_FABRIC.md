# Knowledge Fabric

CHIMERA-ONE treats source, specifications, tests and evidence metadata as a federated knowledge substrate. It does not copy component repositories into this repository.

`chimera-one index` builds a bounded local index from Git-tracked UTF-8 text files in the declared constellation. The generated index is stored under `.chimera/` and is intentionally git-ignored so private source from private component repositories is not republished through the control plane.

The first index is lexical and content-addressed. It records repository authority, path, file class, size and SHA-256 together with a bounded text window for local search. Later retrieval layers may add embeddings or a graph database, but they must retain the repository/path/digest provenance tuple and must never allow retrieved text to silently acquire verification authority.

The knowledge plane is advisory. Verification still belongs to the component that owns the relevant proof boundary.
