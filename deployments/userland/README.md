# UserLAnd Ubuntu build host

This profile turns an Android UserLAnd Ubuntu session into a native CHIMERA build and integration worker. It is intentionally not a production container host and not an evidence-independence boundary.

## Supported role

Use this host for:

- CHIMERA-ONE Python and Rust protocol validation.
- Rust, C and C++ compilation on ARM64.
- Native Aether control-plane and execution-engine builds.
- Chimera-AG deterministic/unit evaluation that does not require unavailable external models.
- RCHAIN-COMPLIER assurance tests, type checks and local loopback workers.
- RitualGraph, CHIMERA-OMEGA and staking-audit offline tests once their repositories are available.
- Git, CMake, Ninja, Protobuf/gRPC, SQLite, shell linting and repository inspection.

## Explicit boundary

UserLAnd is a proot/userspace environment over the Android kernel. Do not treat it as providing Docker Engine, systemd, cgroup isolation, privileged namespaces, production network isolation, or an independent organizational verifier.

Docker image builds, multi-architecture publication, SBOM/provenance generation and container smoke tests remain authoritative in GitHub Actions until a real Linux container host is connected.

A successful build or local process result is an observation. It is not automatically proof, external truth, or independent corroboration.

## Bootstrap

From a CHIMERA-ONE checkout:

```bash
bash deployments/userland/bootstrap.sh
```

The script installs the native build stack, Node 22 via nvm, Rust 1.90.0 via rustup, gRPC/Protobuf development packages, GitHub CLI and small operator utilities. It does not configure GitHub credentials and does not install Docker.

## Workspace

The canonical local workspace root is:

```text
~/chimera/
```

Keep each provider as an independent Git repository under that directory. CHIMERA-ONE should consume provider contracts and repository state rather than copying provider source into its own tree.

For private repositories, authenticate GitHub CLI through the browser/device flow or transfer a Git bundle through an already-authorized local host. Do not commit personal access tokens, SSH private keys, `.env` files or signing keys into the constellation.

## Current reference validation

The first ARM64 UserLAnd reference host established these native signals:

- Aether Rust control plane: 3 unit tests passed.
- Aether C++ execution engine: configured via distro `pkg-config` gRPC fallback and `compute_test` passed.
- Chimera-AG: 80 source tests passed.
- RCHAIN-COMPLIER assurance lane: 13 assurance tests passed, with assurance typecheck and lint passing.

These are host observations, not universal correctness claims.
