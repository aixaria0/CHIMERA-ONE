# Real native capture/build-link occurrence

This is a fresh saved Aether replay verification through ONE using the selected
native x86_64 OMEGA binary from CI run 37707542253. The source/provider revision
is `52a21a8eaa4363d648fdac805900175d81e13f07`; the external build checker is
separately pinned at `9ab2390364fd8c89f29fa46569b58d33ddb61869`.

`capture/` holds the actual invocation receipt, input snapshots and native output.
`build-link.json` holds the actual external build-checker transcript and exact
capture/build selections. `reverify-capture-build.json` records the successful full
raw artifact check performed during acquisition; `validate-capture-build.json`
records saved-link validation. Reading the first report does not perform a new raw
check. `acquisition-controls.json` records 14 saved-link and five real raw-artifact
rejection controls; `provenance.json` preserves acquisition/code/file hashes.

The raw source archives, compiler logs and native binary files remain external
OMEGA artifacts, linked from the OMEGA repository's
`examples/source-build/ci-37707542253/ci-snapshot.json`. Their recorded retention
expiry is 2027-01-06. They are required for a later full re-verification; this
small fixture alone supports only the saved capture/report binding.

The literal selection for this occurrence is independently fixed in the
conformance harness. To validate the saved bytes without private checkout access:

```sh
python3 -m chimera_one validate-capture-build examples/capture-build/native-replay/capture \
  --link examples/capture-build/native-replay/build-link.json \
  --expect-receipt sha256:8832edd572eb04f9cab4f24c082628a66f429dc93ef0945e7cf7025f9ee1861d \
  --expect-link sha256:499bad56abc83a7da78928d6557a6429eacfdbc4e60cee634f33d58a8f103419 \
  --expect-omega-binary 3989b0b32395b21f1d33468e3af65225e36c22ea28fa7e931807bb8b02a54d10 \
  --expect-controller 40346dd9adac3c22401cfd9a83a729c164d2951f2baf692bf74b4316f78caff1 \
  --expect-left-record sha256:02249909a7fbd5e5007785b6f4ceb5621b6ad89a34c0f3d4669784e6b9ccad26 \
  --expect-right-record sha256:c050c79699b77eb86afc11c9642d164f4ec364c487dcc1841ab3e1ab6714649a \
  --left-builder builder-a --right-builder builder-b
```

The report explicitly says raw build evidence was NOT_RUN. To reverify the full
external bytes, replace the command with `reverify-capture-build` and supply
`--build-checkout`, `--left-build`, `--right-build` for the three selected external
directories. Native OMEGA and Cargo are not executed by either validation command.
Independence, compiler correctness, complete toolchain closure and freshness
remain UNKNOWN; build execution remains attributed and general claims unassessed.
