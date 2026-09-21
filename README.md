# Sympose

Sympose is a cheap, low-round-trip AI companion for direct dialogue with an
Obsidian vault: a personal agent hub where a persona (Samantha, by default)
talks to the user in tandem with their vault instead of through expensive
multi-call orchestration.

## Current status

No source tree exists yet. A first vault-dashboard backend and frontend
were built, then deleted (2026-09-22): both were salvaged from
`sympose-legacy` with far less filtering than intended — the frontend
alone carried 60+ comments referencing legacy decision records that don't
exist in this repo, plus dead code left over from features this backend
never had. Starting over from an actual empty slate.

## Project layout

- `profiles/` — persona definitions. Only `samantha.yaml` (the shipped
  default) is committed; any other profile is a personal customization
  and stays local-only (see `.gitignore`).
- `docs/` — engineering standards (`COLLABORATION_STANDARDS.md`,
  `CODE_QUALITY_STANDARDS.md`) and architecture decision records
  (`decisions/`).

## Local setup

Nothing to install yet. `.env.example` shows the one config variable
(`MASTER_VAULT_PATH`) the last implementation relied on, kept as a
reference for whatever rebuilds next.

See `CLAUDE.md`'s Primary Commands section — fill it in once real code
lands.

## Standards and decisions

- `docs/COLLABORATION_STANDARDS.md` — tone, pacing, and working practices.
- `docs/CODE_QUALITY_STANDARDS.md` — the engineering process: tooling,
  review tiers, verification discipline, commit hygiene.
- `docs/decisions/` — architecture decision records; see its `README.md`
  for the index.
- `CONTRIBUTING.md` — repository hygiene (commit authorship, no AI
  tooling artifacts committed).
