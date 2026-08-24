---
name: "git_workflow"
title: "Git Hygiene & Atomic Branch Workflows"
description: "Disciplined version control conventions, atomic commits, conventional commit syntax, and branch safety."
tags:
  - engineering
  - git
  - devops
mcp_servers:
  - "github"
---

# 🌲 Git Workflow & Commit Discipline

When inspecting, generating, or proposing git operations, follow these non-negotiable engineering heuristics:

## 1. Atomic Commit Protocol
- **Single Intent**: Each commit must represent a single logical change (one fix, one feature, one refactor).
- **Conventional Commits**: Format commit messages strictly as `<type>(<scope>): <concise present-tense imperative description>`
  - `feat`: A new feature or capability
  - `fix`: A bug fix
  - `refactor`: Code restructuring without changing observable behavior
  - `perf`: Performance optimization
  - `docs`: Documentation updates only
  - `test`: Adding or updating tests
  - `chore`: Build scripts, dependencies, or tool configurations

## 2. Safety & Branching Directives
- **Zero Force-Pushes to Protected Branches**: Never suggest `git push --force` or `-f` on `main`, `master`, or production branches. Use `--force-with-lease` on feature branches if rebasing.
- **Inspect Before Staging**: Always verify status and diff before proposing a commit:
  ```bash
  git status --short
  git diff --staged
  ```
- **Branch Naming**: Use lowercase kebab-case prefixed with purpose:
  - `feat/feature-name`
  - `fix/issue-description`
  - `chore/dependency-upgrade`

## 3. Pull Request Synthesis Heuristics
When reviewing or summarizing PRs:
1. **The 'Why'**: State the business or technical motivation in 1–2 sentences.
2. **Key Architectural Changes**: Highlight changed interfaces, schemas, or public APIs.
3. **Risk & Rollback Strategy**: Call out migration needs, environment variables, or breaking changes.
