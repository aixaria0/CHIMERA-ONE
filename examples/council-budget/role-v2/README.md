# Real saved native experiment, not a ONE invocation capture

These unmodified files were acquired by personally owned Chimera-AG
[run 37719874307](https://github.com/aixaria0/Chimera-AG/actions/runs/37719874307),
attempt 1, on provider revision `6c529e802833903db75b6f8358031082a8373b2b`.
The tested merge-preview tree equals provider tree
`173afbde5f5d058fe2fad59da856617ab977d05f`.

[Artifact 11525248213](https://github.com/aixaria0/Chimera-AG/actions/runs/37719874307/artifacts/11525248213)
ZIP bytes were downloaded, bounded, checked for exact inventory and SHA-256:
`c84a35c7c9691958dd3391b54ec5a1ad516d681368de1deef5759a3220bd0b38`.
The raw benchmark was recomputed through its pinned source checker without
inference before retention. No mock transport was involved in acquisition.

| Selection | Pin |
|---|---|
| Report | `sha256:a8535cfbfaf91077ff4cafee8da535f3c23ee686f61056fb7d6d2903ff299489` |
| Suite | `sha256:719e63742eff6937a1f436685b4b67ed0a1a52e37f4756191a0beef9b57ca185` |
| qwen2.5:1.5b reported model manifest | `sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b` |

There are twelve paired occurrences from six tasks and 48 native requests per
arm. The single-model arm delivered 6/12 correct answers. Council generated
6/12 correct candidates, delivered 1/12 correct answers and falsely accepted
four answers. Input/output tokens and runtime were unequal despite equal request
caps. Twelve saved-transcript substitution controls passed.

This is a negative diagnostic fixture, not a Council win, training holdout, AGI
assessment or proof of model/operator independence. Acquisition remains
attributed. Unit tests may reuse these saved bytes with explicitly identified
process doubles; that does not create new inference evidence.

With the external AG checkout pinned to the above revision, recompute without
Ollama or any inference:

```sh
cd /tmp/owned-chimera-ag
python -B -m chimera.budget_benchmark validate \
  --suite /path/to/CHIMERA-ONE/examples/council-budget/role-v2/suite.json \
  --report /path/to/CHIMERA-ONE/examples/council-budget/role-v2/benchmark.json \
  --expect-report sha256:a8535cfbfaf91077ff4cafee8da535f3c23ee686f61056fb7d6d2903ff299489 \
  --expect-suite sha256:719e63742eff6937a1f436685b4b67ed0a1a52e37f4756191a0beef9b57ca185 \
  --expect-model sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b
```
