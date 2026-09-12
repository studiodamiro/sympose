/**
 * Inline `#tag` occurrences in a note body, deduped, lowercased, in
 * first-seen order — feeds the frontmatter `tags:` merge on save (the
 * inline-body and frontmatter tag spaces stay in sync one-directionally:
 * new body tags get added to frontmatter, removing one from the body never
 * removes it from frontmatter).
 *
 * Mirrors stylo's own live `tagSource` trigger rule exactly where the two
 * overlap — `#` must sit at start-of-line or after whitespace (never
 * mid-word or a URL fragment), and a digit right after `#` doesn't count
 * (`#1234`, an issue/anchor reference) — plus one step stylo gets for free
 * from CodeMirror's parser that a plain-text scan doesn't: fenced and
 * inline code are stripped first, so `#include`, `#define`, a shebang, or a
 * CSS `#fff` never becomes a tag.
 *
 * The character set is capped to `[a-zA-Z0-9_/-]` — narrower than stylo's
 * own "anything but whitespace/#" query, so a tag ending a sentence
 * (`#project.`) extracts as `project`, not `project.`. Matches the one
 * existing precedent in the codebase (`_sync_frontmatter_tags` in
 * `vault.py`), plus `/` for Obsidian-style nested tags (`#journal/engineering`
 * is one tag named "journal/engineering", not two — consistent with this
 * project's own docs frontmatter).
 */
export function extractInlineTags(body: string): string[] {
  const stripped = body.replace(/```[\s\S]*?```/g, " ").replace(/`[^`\n]*`/g, " ")
  const pattern = /(?<=^|\s)#(?!\d)([a-zA-Z0-9_/-]+)/g
  const seen = new Set<string>()
  for (const match of stripped.matchAll(pattern)) {
    const tag = match[1]?.toLowerCase()
    if (tag) seen.add(tag)
  }
  return [...seen]
}
