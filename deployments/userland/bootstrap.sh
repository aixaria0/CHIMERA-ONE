#!/usr/bin/env bash
set -euo pipefail

RUST_TOOLCHAIN="${RUST_TOOLCHAIN:-1.90.0}"
NODE_MAJOR="${NODE_MAJOR:-22}"
NVM_VERSION="${NVM_VERSION:-0.40.3}"

sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ca-certificates curl git gh git-lfs jq ripgrep rsync shellcheck sqlite3 \
  python3 python3-pip python3-venv python3-dev \
  build-essential clang cmake ninja-build pkg-config \
  protobuf-compiler protobuf-compiler-grpc libprotobuf-dev libgrpc++-dev \
  libssl-dev openssl
sudo apt-get clean

export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh" | bash
fi
# shellcheck source=/dev/null
. "$NVM_DIR/nvm.sh"
nvm install "$NODE_MAJOR"
nvm alias default "$NODE_MAJOR"
nvm use "$NODE_MAJOR"

if [ ! -x "$HOME/.cargo/bin/rustup" ]; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --profile minimal --default-toolchain "$RUST_TOOLCHAIN"
fi
# shellcheck source=/dev/null
. "$HOME/.cargo/env"
rustup toolchain install "$RUST_TOOLCHAIN" --profile minimal
rustup default "$RUST_TOOLCHAIN"
rustup component add rustfmt clippy --toolchain "$RUST_TOOLCHAIN"

git lfs install --skip-repo >/dev/null 2>&1 || true
mkdir -p "$HOME/chimera" "$HOME/.tmp"
chmod 700 "$HOME/.tmp"

PROFILE_MARKER='# CHIMERA automation toolchains'
if ! grep -Fq "$PROFILE_MARKER" "$HOME/.profile" 2>/dev/null; then
  cat >> "$HOME/.profile" <<'PROFILE'

# CHIMERA automation toolchains
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
PROFILE
fi

printf 'Node: '; node --version
printf 'npm: '; npm --version
printf 'Rust: '; rustc --version
printf 'Cargo: '; cargo --version
printf 'Python: '; python3 --version
printf 'CMake: '; cmake --version | head -1
printf 'protoc: '; protoc --version
printf 'GitHub CLI: '; gh --version | head -1
printf 'Workspace: %s\n' "$HOME/chimera"
printf 'Free disk: '; df -h "$HOME" | awk 'NR==2 {print $4}'

echo 'UserLAnd host ready for native CHIMERA builds. Docker remains delegated to GitHub Actions or a real Linux container host.'
