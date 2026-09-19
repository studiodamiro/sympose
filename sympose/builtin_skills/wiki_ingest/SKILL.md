---
name: "wiki_ingest"
title: "LLM Wiki Ingest"
description: "Files a raw source into wiki pages under your assigned Wiki folder (ADR-132/133) and logs the event."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "ollama/gemma2:9b"
minimum_capability_tier: "standard"
tags:
  - wiki
  - ingest
  - obsidian
---

# LLM Wiki Ingest

Tag syntax and "markdown in chat ≠ a file on disk" are in the base rules.
This playbook is what to do with a raw source you've been handed: turn it
into wiki pages, never touch the source itself, and leave a record.

**Ground rule.** Your `vault_folders` sandbox for this persona *is* the
wiki root — every write below stays inside it. If you're not sure what
that folder is called, check the `WIKI.md` schema file at its root; it's
seeded there for exactly this reason.

## What "ingesting" means

1. **Read the source, don't touch it.** Whatever's under the wiki root's
   `Sources/` subfolder (or handed to you directly in the task) is raw
   material — quote it, summarize it, never rewrite it in place.
2. **Write or update wiki pages** — one page per real entity/concept/topic
   the source covers, not one giant page per source. Reuse an existing
   page (`[APPEND_NOTE]`) if the topic already has one; create a new page
   (`[WRITE_NOTE]`) otherwise. Link pages to each other with
   `[[Wikilink]]` where they genuinely relate — this is what keeps a page
   from becoming an orphan later.
3. **Write your own frontmatter, including a one-line `summary:`.** The
   folder's default template can't fill this in for you (it has no way to
   know what the page is about) — `[WRITE_NOTE]`'s payload should start
   with an explicit frontmatter block instead of relying on the folder's
   template:
   ```
   [WRITE_NOTE: <topic>.md | ---
   title: <Topic>
   tags: [wiki]
   summary: <one honest sentence — what this page actually says>
   ---

   <the page body>]
   ```
4. **Log the ingest.** After filing the source, `[APPEND_NOTE]` one line
   to the wiki root's `log.md` — timestamp, the source, and which pages
   you touched:
   ```
   [APPEND_NOTE: log.md | 2026-09-19 14:02 — ingested "some-article.md" → wrote [[Topic A]], appended [[Topic B]]]
   ```

## What you're not doing

- Not inventing content the source doesn't support — the same
  anti-fabrication ground rule as everywhere else in Sympose applies here:
  a summary is a compression of what's actually there, never a guess.
- Not running a health check across the whole wiki — that's the
  `wiki_lint` skill's job, a separate, explicitly-requested pass.
- Not writing anywhere outside your assigned folder, even if a source
  seems to belong somewhere else in the vault — flag it in your reply
  instead of reaching past your sandbox.
