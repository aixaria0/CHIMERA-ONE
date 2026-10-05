.PHONY: test python-test rust-test rust-lint conformance docker-build docker-check federation

test: python-test rust-lint rust-test conformance

python-test:
	python3 -m unittest discover -s tests -v

rust-lint:
	cargo fmt --all -- --check
	cargo clippy --workspace --all-targets --locked -- -D warnings

rust-test:
	cargo test --workspace --locked

conformance:
	python3 -m chimera_one protocol-validate tests/vectors/run.valid.json
	cargo run --quiet --locked -p chimera-protocol -- validate-run tests/vectors/run.valid.json

docker-build:
	docker build --build-arg SOURCE_REVISION=$$(git rev-parse HEAD) -t chimera-one:dev .

docker-check:
	docker compose run --rm control-plane
	docker compose run --rm protocol-check

federation:
	python3 -m chimera_one federation --workspace ..
