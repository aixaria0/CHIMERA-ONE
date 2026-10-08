# Checked-program routing policy v1

This policy connects one reviewed Chimera-AG native acquisition to ONE without
rerunning inference or treating model agreement as truth. It applies only to
integer `a*b+c`, bounded state transitions and directed reachability. Models
proposed JSON data programs; fixed local algorithms produced answers; a separate
typed implementation checked them.

## Selected evidence

| Selection | Pin |
|---|---|
| Provider source | `efe372e1065f0cfdb8f3cafee0264632d54dc98f` |
| Provider tree | `ddfd4b1e09d0ba002f4f50292ffe87cf28d4cfb6` |
| Native run | `37821064387` |
| Artifact | `11570730020` |
| Artifact ZIP | `sha256:d0cbd4821fb4ccfc2b98ed62db0604421d6aad648d7b58f5bcc1cd5b2550c1c9` |
| Model manifest | `sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b` |
| ONE evidence | `sha256:a010084f89462aadd7b8e4c9e498fe54264ee69cbd77dfa70b1a78ddbcc393b9` |
| ONE policy | `sha256:4cd4fa71c6eea86b31f76b72c0b4603a5f1a66794a569f88e1296668fe31e319` |

The artifact was downloaded and checked against its byte size and ZIP digest.
Both native reports, source hashes, program selections, fixed answers and all 34
saved substitution controls were recomputed locally without inference before
the compact ONE evidence record was authored.

| Suite | Four single samples | Council | Single elapsed | Council elapsed |
|---|---:|---:|---:|---:|
| Regression | 12/12 | 12/12 | 112.102 s | 251.418 s |
| Transfer | 12/12 | 11/12 | 112.040 s | 256.843 s |

Both arms used 48 native requests per suite and produced zero false accepts.
The rejected Council occurrence reordered `multiply` and `set`; exact operation
binding blocked delivery.

## Decision rule

`derive-program-policy` selects `SINGLE_FOUR_SAMPLE_CHECKED_PROGRAMS` only when,
on each of the two exact suites:

- both arms have zero false accepts and 48 requests;
- the single arm has at least as many verified answers as Council; and
- the single arm has lower observed elapsed time.

Otherwise it emits `NO_SELECTION`. This is a closed rule over externally pinned
saved evidence. It does not run a model, change a provider, execute a generated
program or authorize a general planner step. It selects four checked samples,
not a one-call route; reducing request count requires another matched experiment.

```sh
python -m chimera_one derive-program-policy \
  --evidence examples/program-routing/v3/evidence.json \
  --expect-evidence sha256:a010084f89462aadd7b8e4c9e498fe54264ee69cbd77dfa70b1a78ddbcc393b9 \
  --output /tmp/program-policy.json

python -m chimera_one validate-program-policy /tmp/program-policy.json \
  --evidence examples/program-routing/v3/evidence.json \
  --expect-evidence sha256:a010084f89462aadd7b8e4c9e498fe54264ee69cbd77dfa70b1a78ddbcc393b9 \
  --expect-policy sha256:4cd4fa71c6eea86b31f76b72c0b4603a5f1a66794a569f88e1296668fe31e319
```

Training-data independence, tool CPU equality, runtime attestation, performance
outside the three selected task families, collective superiority and general
intelligence remain unestablished. The router performs no automatic promotion.
