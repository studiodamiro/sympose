---
entry: 2026-09-07
created: 2026-09-07 16:45
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/performance
  - sympose/dashboard
---

# Sympose Engineering Log: Prompt-Cache Preservation & HTTPS Opt-In

> **Date:** Sunday, September 7, 2026
> **Topic:** Two small refinements found while debugging local-model Slack
> latency — a per-minute token that was invalidating the local prompt cache,
> and an interactive HTTPS choice for the dashboard (ADR-064.2)
> **Participants:** damiro (Lead Architect), Claude (Sonnet 5) (Engineering Partner)
> **Status:** Implemented, tested; skills work recorded separately in ADR-076.

---

## 1. The prompt-cache regression

Anaïs (a diarist persona on a 14B abliterated Ollama model) was taking ~60 s to
first token on **every** Slack turn — not just the first after a cold model
load. A three-turn probe against a warm model showed 60 s / 60 s / 60 s: no
prompt-cache reuse at all between turns of the same conversation.

The cause was in `ProfileManager.build_system_prompt`
([profiles.py:247](../../../sympose/profiles.py#L247)): the
`{{current_datetime}}` substitution used `strftime("%Y-%m-%d %A %H:%M")` — with
minutes — and the "Current Date & Time" line sits about 6 % into the assembled
system prompt (in the Runtime Environment block). llama.cpp's prompt cache
matches a **prefix**; the moment the clock ticked, the match broke ~337 tokens
in and the remaining ~5,100 tokens re-prefilled from scratch, every turn, at
~80 tok/s ≈ 60 s.

**Fix:** drop the time component — `strftime("%Y-%m-%d %A")`. Date-only keeps
the prefix stable for a whole day. Nothing else consumes `{{current_datetime}}`;
every write-time timestamp (daily-note `### Reflection (HH:MM)` headers, session
log frontmatter) uses its own `datetime.now()` and is unaffected.

Measured after the fix, warm model, same session:

| turn | before | after |
| --- | --- | --- |
| 1 | 60.1 s | 60.1 s |
| 2 | 60.0 s | 6.5 s |
| 3 | 60.0 s | 0.5 s |

So the first message in a Slack thread still pays the full prefill; every
follow-up in that thread is now near-instant. Cutting the first-turn cost is a
prompt-size problem, addressed separately in
[ADR-076](./2026-09-07_adr-076-skill-playbook-single-source-and-compression.md)
(skill playbook compression took Anaïs's prompt 5,471 → 2,745 tokens, first
token ~60 s → ~39 s).

This is a general local-inference lesson: **no volatile token belongs high in a
cached system prompt.** Recorded in the latency-tuning guide.

## 2. Dashboard HTTPS opt-in (ADR-064.2 refinement)

[ADR-064.2](../2026-08/2026-08-30_adr-064-dashboard-api-auth-plan.md) shipped
self-signed TLS as the default, toggled only by `SYMPOSE_DASHBOARD_TLS=0`. In
practice the dashboard binds to `127.0.0.1` only, where plain HTTP is exactly as
private as HTTPS — the self-signed cert buys nothing but a browser "not secure"
click-through on first use per device.

**Change:** `sympose/tls.py` gains `ensure_dashboard_tls_choice(workspace_dir)`,
following the same generate-once-and-persist pattern as the dashboard password.
On the first interactive `--dashboard` boot it asks (rich `Confirm`, default
yes) and appends the answer to the workspace `.env`; a pre-set
`SYMPOSE_DASHBOARD_TLS` or a non-interactive launch skips the prompt. `app.py`
calls it instead of reading the env var inline; `server.py`'s startup banner
moved from three `log.info` lines to two `print`s so the URL and credentials are
always visible regardless of log level. Covered by `tests/unit/test_tls.py`.

## 3. Verification

- `.venv/bin/pytest` — 157 passing (includes the new `test_tls.py` and the
  ADR-076 `DEFAULT_RULES_MD` guard).
- Prompt-cache: the three-turn latency table above, measured live against the
  running Ollama server with the 14B model resident.
- HTTPS opt-in: `test_tls.py` covers the pre-set / non-interactive / prompted
  paths; the persisted `.env` line is asserted.

## 4. Why no ADR for §1

A one-line `strftime` format change with no architectural trade-off and no
reversal cost. It refines the prompt-assembly already covered by ADR-070's
hot-path budget discipline. §2 is an implementation refinement of ADR-064.2, not
a new decision. Journaled per the documentation standard.
