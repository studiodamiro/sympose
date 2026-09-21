# Code Quality Standards

> Drop this file in as `docs/CODE_QUALITY_STANDARDS.md` in a new project.
> `CLAUDE.md` and `GEMINI.md` both point here so the two assistants follow
> the same process instead of drifting apart. Replace `[PROJECT NAME]`
> below, and trim anything that genuinely doesn't apply — but don't trim
> anything just because it's inconvenient this week.

These standards came out of a real, full-codebase cleanup on **Sympose**
and the working rules already proven on **Stylo** (2026-09), not out of a
generic best-practices list. Every rule below either caught a real bug,
closed a real gap, or prevented a real kind of wasted effort on one of
those projects. Keep it that way going forward: don't add a rule here on
theory — add it once it's paid for itself, the same way the ones below did.

## 0. Before you write any code

These are standing working-practice rules, not audit findings — they apply
to every task, not just a cleanup pass.

- **Think before coding.** Ask 1–3 clarifying questions on ambiguous
  requests instead of guessing — no more; over-asking is its own way of
  stalling. State the implementation steps before executing them on
  anything non-trivial, and surface any edge cases or conflicts with the
  existing architecture up front, before they turn into a mid-task
  surprise. Treat a design critique or question as a discussion prompt,
  not an order to go implement something — confirm scope first.
- **Touch only what the task requires.** A bug fix doesn't need
  surrounding cleanup bundled in; a one-shot change doesn't need a new
  abstraction built around it. If a rule-set adoption or similar task
  genuinely requires fixing a few small pre-existing issues to start clean
  (see §2), say so explicitly and keep it small — that's a stated
  exception, not a license for drive-by refactors.
- **Diagnose before guessing.** When an implementation fails or stalls,
  find the actual root cause before changing anything else. Trial-and-error
  edits made without understanding *why* the last one didn't work tend to
  compound rather than converge.
- **Simplest solution, fewest lines.** Default to the most direct
  implementation that satisfies the request. Prefer composing existing
  primitives over adopting a new framework or pattern for one use case.
- **Single Responsibility + a real file-size cap.** "Keep files small" is
  an unenforced platitude until it's an actual number. Pick one
  appropriate to the language and project (Sympose uses 200 LOC per file
  for its Python package) and hold to it. For a library, keep the public
  entry point a thin barrel — re-exports and types only, no logic — so
  consumers have one obvious place to see the whole surface area.
- **Config/runtime knobs declared once.** A setting lives in exactly one
  canonical place (a schema file, a constants module — whatever the
  project's equivalent is). Never re-declare its default as a literal at
  each call site; every call site reads the one canonical value.
- **No new dependency without a decision record.** This is the hard-gate
  version of §9 below, specifically for dependencies: don't add one
  because it's convenient. Before proposing one, check it's modular (no
  pulling in a large tool to use one function) and license-compatible with
  the project; the resulting decision record must weigh it against at
  least one lighter alternative, not just justify the choice made.
- **Directory / path-boundary safety.** Any code that accepts a path
  derived from user input or external data must validate it stays within
  its intended root *before* touching the filesystem — resolve to a real
  (canonical, symlink-resolved) path first, then check containment against
  the allowed root. A string-prefix check alone is not enough.
- **Thread safety & process lifecycles.** Shared mutable state touched
  from more than one thread, request, or instance needs explicit
  synchronization or per-instance isolation — this is exactly the
  `SlackDaemon` bug this audit found: three caches declared at class level
  that should have been per-instance, so every persona silently shared one
  cache instead of having its own. Any background process/subprocess the
  app spawns needs explicit cleanup (an `atexit` handler or equivalent) so
  it doesn't outlive the app.

## 1. Tooling: real dev dependencies, not ad hoc

- Install a real linter / formatter / type-checker as a **declared dev
  dependency** (`package.json` devDependencies, `pyproject.toml`'s
  `[project.optional-dependencies].dev`, or the language's equivalent) —
  not something run once from a global install and forgotten.
- Persist its configuration **in the repo** (`eslint.config.js`,
  `pyproject.toml`'s `[tool.ruff]`, `tsconfig.json`, etc.) so a fresh clone
  reproduces the exact same checks. A check that only lives in someone's
  shell history isn't a standard — it's a one-off.
- Typical stack: TypeScript + ESLint for JS/TS frontends; `ruff` for
  Python backends. Pick whatever is idiomatic for the language, but always
  both a *linter* (style/correctness patterns) and, where the language
  supports it, a *type checker* — they catch different things.

## 2. Start narrow. Earn every rule category.

- Don't flip on a big default/preset rule set on day one. Enable a
  category, run it, and actually read what it flags before deciding it's
  worth keeping on.
- If a category surfaces a wall of pre-existing, unreviewed findings on an
  established codebase: either fix them all before adopting it as a
  standing rule, or leave it off for now — and write down why (see §9).
- Explicitly record what you *deliberately did not* enable, and why. That
  list is as valuable as the enabled list — it's what stops someone later
  "helpfully" turning on everything and burying the signal in noise nobody
  asked for.

## 3. Three distinct tiers of review — don't let one substitute for another

1. **Architecture / design review** — does the system's shape make sense.
   Judgment call, no tool does this for you.
2. **Automated tooling** — style, known-bad patterns, security
   anti-patterns, type mismatches. Fast and mechanical; it catches a class
   of problem a human gets bored of checking by hand, and nothing more.
3. **Manual correctness / algorithm review** — does the logic actually do
   what it's supposed to, on the inputs that matter. A linter does not
   check this. Scope it deliberately (§5) instead of trying to read an
   entire codebase end to end.

If someone asks "have we really checked everything," the honest answer
names which of these three actually happened, not just "yes."

## 4. Triage findings by what they're worth, not by how many there are

- **Mechanical / auto-fixable** (formatting, unused imports, simple
  renames): batch-fix, re-run the test suite, move on. Low judgment
  needed, low risk.
- **"This pattern is often a bug" findings** (broad exception catches,
  complexity flags, etc.): read each one and trace what actually happens.
  On the Sympose audit, ~110 broad `except Exception` catches turned out
  to already be correct (deliberately broad, or re-raised), while a
  smaller, different set of 35 were genuinely silent failures worth
  fixing. The true-positive rate differs wildly by category — never
  blanket-apply one fix pattern across a whole rule category without
  actually checking each hit.
- Use a complexity/hotspot signal (cyclomatic complexity, file churn, file
  size) to **scope** a manual review — it means "worth a careful read,"
  not "confirmed bug."

## 5. How to run the correctness / algorithm review

- Scope it to the highest-complexity or most tightly-coupled
  functions/files first, not the whole tree.
- Read each one fully. Trace the actual control flow against real inputs,
  including edge cases the code visibly hasn't considered.
- **Try to disprove your own finding before reporting it.** Trace the
  surrounding code to check whether the apparent problem is already
  handled somewhere else. Report only what survives that check — this is
  what keeps a review's findings trustworthy instead of a pile of
  maybes.
- For a security-relevant finding: report the mechanism and a concrete,
  plausible failure scenario. Don't construct or run a working exploit
  unless explicitly asked to — describing the risk doesn't require
  weaponizing it.
- When a detection mechanism is fundamentally fuzzy (e.g., a regex that
  can't fully disambiguate an edge case), prefer a small fail-closed
  hardening (reject the ambiguous case outright) over trying to perfect
  the fuzzy mechanism itself.
- Verify every fix against the existing test suite, and add a manual
  sanity check for anything behaviorally subtle the suite doesn't already
  cover.

## 6. Type safety (TypeScript, or any statically typed language)

- No blind escape hatches (`any`, unchecked casts, un-narrowed `unknown`)
  used just to make the compiler stop complaining. If a library exports
  generics for a data shape (e.g. a graph/rendering library's
  `NodeObject<T>`), use them instead of re-inventing or widening to `any`.
- Build the smallest, most accurate local type that reflects what the code
  actually does at runtime — including fields a third-party library
  mutates onto an object after the fact — rather than the broadest type
  that happens to compile.
- After a typing pass, verify **both** the linter and the type checker.
  A change can be lint-clean and still fail type-checking, or vice versa;
  neither substitutes for the other.
- When removing a cast or an `any`, re-derive the actually-correct type.
  Don't stop the moment the red squiggly disappears — a wrong-but-quiet
  type is worse than an honest, visible `any`.

## 7. Verification discipline — no claiming done without evidence

- Every gate the project has must pass before any change is reported
  complete — typecheck, lint, the full test suite, and the build, not
  whichever subset is quickest to run. Re-run them after every meaningful
  edit, not only once at the very end.
- If there's a build step, it must succeed — and for anything UI-facing,
  actually load the feature and interact with it, don't just trust a green
  build.
- If you can't verify something yourself (no browser available, can't run
  the affected service, etc.), **say so explicitly** rather than inferring
  success from static checks alone. "Typecheck and lint are clean; I
  couldn't click through the UI myself — can you take a look?" beats a
  confident claim that can't be backed up.
- Read the actual diff before it's committed, not just a summary of the
  intended change — this is what catches anything that slipped in beyond
  the stated scope.

## 8. Commit hygiene

- Split commits by logical concern (e.g. frontend vs. backend, mechanical
  cleanup vs. judgment-based bug fixes) — the way a reviewer would want to
  read the history, not one giant commit for a multi-day cleanup.
- Commit messages explain **why**, not just what — the failure mode a fix
  closes, the reasoning behind a tooling choice — not a restatement of the
  diff.
- Respect the repo's own attribution conventions (e.g. no AI co-author
  trailer, if that's the standing preference). Check for a project or
  personal standing instruction before defaulting to a harness's generic
  behavior.

## 9. Lightweight decision records for anything durable

- Any new dependency, or any decision that outlives the current task (a
  new lint standard, a security-hardening approach, an architecture
  change), gets a short written record: **Context, Decision, Consequences,
  Alternatives rejected.**
- The "Alternatives rejected" section is not boilerplate. It's where you
  write down what you deliberately did *not* do, and why — so a future
  reader (including future-you) doesn't have to re-litigate it or wonder
  whether it was simply overlooked.
- Keep an index of these records (even a single markdown table) so they're
  discoverable, not buried in commit history.

## 10. Communication style while doing this work

- Plain-language explanations for a non-coder stakeholder — translate a
  rule code or a stack trace into what it actually means ("this piece of
  state was accidentally shared between every instance instead of being
  separate per object"), not just the label.
- Clearly distinguish "I fixed X" (verified) from "I'm flagging X for your
  judgment" (a real risk or tradeoff, not a clear-cut bug).
- Ask before large, risky, or hard-to-reverse changes (a mechanical
  reformat touching every file, a new standing dependency). A short
  confirmation costs little; redoing unwanted work costs a lot.
- State findings and decisions directly. Skip narrating the process
  ("I'm now going to...") — say what you found and what you did about it.

## 11. Zero-bloat, applied to tooling too

- Don't add abstractions, dependencies, or automation beyond what the
  current, real need justifies — including these standards themselves.
  Adopt the rule categories that found real problems on *this* codebase,
  not the ones that merely sound thorough.
- When turning on a new standard against an existing codebase, fix
  whatever small pre-existing issues it surfaces first, so the standard
  starts from a clean baseline instead of shipping with day-one
  exceptions nobody will ever get around to.

---

*Adapted from the Sympose code-quality audit and Stylo's execution
guidelines (2026-09). See Sympose's `docs/journal/` ADRs for the concrete,
worked example §§1–9 were generalized from.*
