# Build and supply-chain policy

CHIMERA-ONE uses two implementation layers deliberately:

- Python is the control-plane interface, repository intelligence layer and planner.
- Rust is the deterministic protocol validation and digest kernel.

The Rust kernel does not perform arbitrary execution, network access or autonomous mutation. It validates bounded protocol records, enforces fail-closed run-policy invariants, checks DAG references/cycles, and computes domain-separated canonical digests.

## Reproducibility

- Rust MSRV/toolchain is pinned to 1.90.0 to align with the CHIMERA-OMEGA evidence kernel lineage.
- `Cargo.lock` is committed and CI uses `--locked`.
- Container builds use explicit Debian-based Rust/Python image versions and multi-stage builds.
- Runtime containers execute as non-root, drop Linux capabilities, use `no-new-privileges`, and are read-only by default.
- Provider source trees are mounted read-only when federation checks run in containers.

## CI gates

Every push and pull request must pass Python tests, Rust formatting, Clippy with warnings denied, Rust tests, and cross-language protocol conformance.

Container CI builds linux/amd64 and linux/arm64 images. Main/tag builds are pushed to GHCR with BuildKit SBOM and provenance attestations. Docker BuildKit attestations are used because this repository is private; GitHub artifact attestations for private repositories require GitHub Enterprise Cloud according to GitHub's current documentation.

## Security maintenance

A scheduled workflow runs RustSec `cargo audit`, lockfile checks and protocol self-tests. Dependabot tracks Cargo, Docker base images, Python packaging and GitHub Actions.

No workflow receives broad write permission unless its job must publish an artifact. Container publication receives only `contents: read` and `packages: write`.

## Local environments

The current Android/Termux control host has Rust, Cargo, Python, Node and protoc, but no Docker/Podman/nerdctl. Local source and Rust/Python tests remain first-class there. Container builds are authoritative in GitHub Actions until a Docker-capable builder is connected.
