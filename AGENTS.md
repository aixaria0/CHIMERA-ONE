# Personal repository and execution boundary

- Work only in repositories personally owned by the user, currently `aixaria0`.
  Preserve existing repositories, histories and original checkout state. Use
  isolated branches/worktrees for engineering and disposable state for tests.
- No changes, issues, PRs, comments, pushes, clones for operational experiments,
  or other effects in contributor/upstream repositories owned by others.
- The now-public testnet and shared/public nodes are off-limits: no connection,
  query, deployment, transaction, validator action, load test or reproduction.
- Prefer offline saved evidence. Runtime fixtures must be personally owned,
  disposable and local. Do not execute the staking-audit operational target or
  RCHAIN-COMPLIER upstream/devnet workflows as an integration shortcut.
- Review CI side effects before publication. Ordinary build dependencies and
  personally owned source checkouts are allowed; third-party operational targets
  are not. Do not add credentials or public-node configuration to enable tests.
- Capabilities and provider manifests describe contracts; they do not authorize
  arbitrary command execution. Keep any executable adapter explicitly bounded.
- Keep source/binary/context/evidence pins distinct. Preserve native reports,
  UNKNOWN and NOT_RUN dimensions; captured provider success is not claim truth.
- Report changes as completed only after a real Git commit exists. Reproduce
  positive and negative controls and verify the exact published commit/tree.
- Do not delegate to subagents unless the user explicitly asks for delegation.
