---
name: "git_workflow"
title: "Git Hygiene & Atomic Branch Workflows"
description: "Atomic commits, conventional-commit syntax, and branch safety."
tags:
  - engineering
  - git
  - devops
mcp_servers:
  - "github"
---

# Git Workflow & Commit Discipline

**Atomic commits** — one logical change per commit. Message format:
`<type>(<scope>): <present-tense imperative>`, type ∈ `feat` / `fix` /
`refactor` / `perf` / `docs` / `test` / `chore`.

**Branch safety** — never `git push --force` / `-f` on `main`, `master`, or a
production branch; use `--force-with-lease` on feature branches when rebasing.
Inspect before staging (`git status --short`, `git diff --staged`). Branch names
are kebab-case with a purpose prefix (`feat/…`, `fix/…`, `chore/…`).

**PR synthesis** — state the why in 1–2 sentences; call out changed
interfaces/schemas/public APIs; note migrations, new env vars, and breaking
changes with a rollback path.
