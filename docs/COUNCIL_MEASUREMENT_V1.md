# Pinned local Council measurement

`measure-chimera-council` is one explicit bounded invocation of personally owned
Chimera-AG. The general planner still emits a plan. This adapter executes neither
arbitrary catalog commands nor generated code. It copies four pinned Python
modules into a temporary private runtime snapshot; component source is not
vendored into ONE.

## Select and acquire

The exact provider source is `aixaria0/Chimera-AG` revision
`6c529e802833903db75b6f8358031082a8373b2b`, tree
`173afbde5f5d058fe2fad59da856617ab977d05f`. The adapter checks canonical origin,
clean Git state, manifest bytes/identity and each selected module's SHA-256.
Changing model or suite pins is an explicit new selection, not an automatic
promotion. The selected local model manifest is Ollama-reported, not attested.

On a personally owned POSIX host with Python 3.11+ and Ollama:

```sh
git clone https://github.com/aixaria0/Chimera-AG.git /tmp/owned-chimera-ag
git -C /tmp/owned-chimera-ag checkout --detach 6c529e802833903db75b6f8358031082a8373b2b
ollama pull qwen2.5:1.5b
python -B -m chimera_one measure-chimera-council \
  --chimera-checkout /tmp/owned-chimera-ag \
  --suite examples/council-budget/role-v2/suite.json \
  --expect-suite sha256:719e63742eff6937a1f436685b4b67ed0a1a52e37f4756191a0beef9b57ca185 \
  --model qwen2.5:1.5b \
  --expect-model sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b \
  --repeats 2 --host http://127.0.0.1:11434 --output /tmp/one-council-capture
```

This is a zero-inference dry run. Add `--execute` to that command to acquire
actual native responses. Existing output directories are refused. A changed
model manifest is rejected before inference. Only literal HTTP IPv4 loopback
ports 1024–65535 are accepted; the provider disables environment proxies and
redirects and rejects cloud model metadata. These checks are not an OS sandbox.

Both arms use four attempted requests per occurrence, 64 output tokens per call,
2048 context tokens and the same seed schedule. The single-model arm requires
three-of-four normalized agreement; Council uses two workers, synthesis and a
model review. Actual spent tokens and time are separate measurements. Identical
caps do not establish identical cost or CPU, and roles share one configured
model. Six public tasks run twice by default; repeats are not independent tasks.
The provider recomputes arithmetic, state transitions and graph reachability
through bounded algorithms. Reference answers never enter inference prompts.

## Capture and saved verification

The fixed child invocation uses isolated Python, no inherited proxy/credential
environment, a 900-second process-group deadline and bounded output. Native
requests have their own 45-second timeout and body/usage bounds. A separate
10-second invocation runs only the pinned saved-transcript checker. It rebuilds
role-bound prompts/options, replays retained Council responses and recomputes
all reference scores, verdicts and usage. It does not run a model.

The seven-file capture contains `inputs/suite.json`, `benchmark.json`,
`provider.stdout`, `provider.stderr`, `checker.stdout`, `checker.stderr` and
`receipt.json`. The receipt binds occurrence UUID, source, selected suite/model,
outcome and artifact hashes/sizes. Suite bytes are capped at 16 KiB, the report
at 1 MiB, each process transcript at 128 KiB and the receipt at 16 KiB. Extra
files, symlinks, special files and changed bytes are rejected. New files have
private permissions. Failed invocation diagnostics remain saved; they cannot
silently become successful measurements.

Independently review the acquisition and select its receipt/report pins. Then:

```sh
python -B -m chimera_one validate-council-capture /tmp/one-council-capture \
  --chimera-checkout /tmp/owned-chimera-ag \
  --expect-receipt sha256:REVIEWED_OCCURRENCE_RECEIPT \
  --expect-report sha256:REVIEWED_NATIVE_REPORT \
  --expect-suite sha256:719e63742eff6937a1f436685b4b67ed0a1a52e37f4756191a0beef9b57ca185 \
  --expect-model sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b
```

Successful saved verification means selected transcripts/scores were recomputed,
with fresh inference NOT_RUN. INCOMPLETE remains incomplete. For a BLOCKED
capture, only an explicit `--expect-report NOT_RUN` enables byte-integrity
verification; its scope is CAPTURE_BYTES_ONLY and no source/model is invoked.
Copying pins from an untrusted receipt is not independent selection.

## Retained diagnostic result and next gate

The retained [actual AG acquisition](../examples/council-budget/role-v2/README.md)
on this exact provider source delivered 6/12 correct single-model answers versus
1/12 correct Council answers, with four false acceptances. Council produced six
correct candidates but its review gate lost five of them. Both arms completed
48 requests. These negative results are preserved; no router/model promotion
follows. Seeds do not establish repeatable native inference; only saved-byte
recomputation is deterministic here.

The ONE PR workflow runs this actual adapter against disposable owned Ollama
weights, then checks saved bytes and seventeen substitution controls without new
inference. It records the tested ONE head/tree, pinned AG source, runtime and raw
capture in a 90-day artifact. No new cross-repository credentials are needed.

This is an evaluation bridge, not demonstrated learning or general intelligence.
Model agreement stays advisory, raw execution stays attributed, role/CPU/training
data independence stays unestablished, host runtime closure stays unknown and
collective superiority stays NOT_ESTABLISHED. The next capability gate is to
replace unreliable model-only acceptance with task-bound independent checking,
then measure on separately frozen unseen tasks under the same resource caps.
