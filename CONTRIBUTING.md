## Repository hygiene

These are strict, not aspirational.

- **Single author identity.** Every commit is authored and committed by the
  repository owner (`damiro <hello.damiro@gmail.com>`). No secondary
  identities, no aliases.
- **No trailers.** Commits carry no `Co-authored-by`, `Signed-off-by`, or
  tooling/attribution trailers of any kind.
- **Assistant and editor tooling is never committed.** `.agents/`,
  `.claude/`, `.gemini/`, `.cursor/`, `CLAUDE.md`, `GEMINI.md`, `.vscode/`,
  and the like are local-only. They're covered machine-wide by
  `core.excludesFile` and, belt-and-braces, by this repo's own
  `.gitignore`. A new repository copies the same block:

  ```gitignore
  # AI assistant & editor tooling — never committed
  .agents/
  .claude/
  .gemini/
  .cursor/
  CLAUDE.md
  GEMINI.md
  ```

- Referring to the underlying models (Claude, Gemini, or others) in code,
  docs, or configuration is fine, where the project's subject matter
  actually involves them. The rule is about authorship and tooling
  artifacts, not the product's subject matter.
