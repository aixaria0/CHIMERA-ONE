# syntax=docker/dockerfile:1.7
FROM rust:1.99.1-bookworm AS rust-builder
WORKDIR /src
COPY Cargo.toml Cargo.lock rust-toolchain.toml ./
COPY crates ./crates
RUN cargo build --locked --release -p chimera-protocol

FROM python:3.14-slim-bookworm AS python-builder
WORKDIR /src
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml README.md ./
COPY chimera_one ./chimera_one
RUN pip install --no-cache-dir --no-deps .

FROM python:3.14-slim-bookworm AS runtime
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/aixaria0/CHIMERA-ONE" \
      org.opencontainers.image.revision="${SOURCE_REVISION}"
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git openssl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 chimera
COPY --from=python-builder /opt/venv /opt/venv
COPY --from=rust-builder /src/target/release/chimera-protocol /usr/local/bin/chimera-protocol
WORKDIR /opt/chimera-one
COPY capabilities ./capabilities
COPY adapters ./adapters
COPY contracts ./contracts
COPY docs ./docs
COPY tests/vectors ./tests/vectors
ENV PATH="/opt/venv/bin:$PATH" \
    CHIMERA_ONE_ROOT="/opt/chimera-one" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001:10001
ENTRYPOINT ["chimera-one"]
CMD ["capabilities"]
