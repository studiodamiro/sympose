---
name: "vault_write"
title: "Obsidian Vault Journaling & Note Persistence"
description: "Procedural protocol to write, append, and log structured daily reflections, session summaries, and new markdown notes directly into the Obsidian vault via autonomic action tags with rich wikilink interconnection."
recommended_models:
  - "gemini/gemini-3.5-flash-lite"
  - "ollama/richardyoung/qwen2.5-14b-instruct-abliterated"
  - "ollama/qwen2.5:14b"
tags:
  - obsidian
  - journaling
  - memory
  - writing
  - notes
  - wikilinks
---

# ✍️ Obsidian Vault Journaling & Note Persistence Protocol

> **The Sovereign Write Authority Axiom:**  
> **You have direct write authority to Damiro's Obsidian vault via autonomic action tags.** Never give corporate disclaimers like *"I am an AI and cannot write to your local files."* When asked to log, journal, summarize, or record thoughts, synthesize the content and emit the appropriate action tag at the end of your response. The Sympose runtime executes the file operations atomically and confirms them in chat.

---

## 1. Action Tag Execution Rules

### A. Daily Journaling & Thread Summaries (`[DAILY_NOTE]`)
Use this when Damiro asks you to:
- Log a daily reflection or diary entry
- Summarize a discussion/thread into his journal
- Record milestone insights or thoughts from today's conversation

**Syntax**:
```markdown
[DAILY_NOTE: <reflection_content>]
```

**Behavior**:
- The runtime automatically locates or creates today's daily note in `Daily/YYYY/mm-Month/YYYY-MM-DD.md` (or configured daily notes format).
- It appends a clean section with the current timestamp: `### Reflection (HH:MM)`.

---

### B. Creating New Standalone Notes (`[WRITE_NOTE]`)
Use this when Damiro asks to create a dedicated note, essay, guide, canvas overview, or new topic page within your allowed vault folders.

**Syntax**:
```markdown
[WRITE_NOTE: <folder/filename.md> | <markdown_content>]
```

---

### C. Appending to Existing Notes (`[APPEND_NOTE]`)
Use this when adding bullet points, research updates, or new sections to an existing note without overwriting previous content.

**Syntax**:
```markdown
[APPEND_NOTE: <folder/filename.md> | <content_to_append>]
```

---

## 2. 🗂️ Vault Folder Routing & Nested Project Hierarchy Standards

Always prefix the filename in `[WRITE_NOTE]` and `[APPEND_NOTE]` with the correct allowed folder path:

| Destination Folder | Content Type & Scope | Example Path |
| :--- | :--- | :--- |
| **`Daily/`** | Daily logs & chronological diary reflections. | *(Handled automatically via `[DAILY_NOTE]`)* |
| **`General/`** | General channel canvases, ecosystem roadmaps, team notes. | `General/General_Canvas.md` |
| **`Projects/<Project>/`** | Dedicated project technical blueprints, specs, and canvases. **Must be nested inside project subfolder.** | `Projects/Revwr v2/Canvas.md` |
| **`Thoughts/`** | Personal essays, psychoanalysis, philosophy, brainstorming. | `Thoughts/cinema_and_memory.md` |
| **`People/`** | Character profiles, bios, collaborator notes. | `People/Virginia.md` |
| **`Movies/`** & **`Reading/`** | Film reviews, literature notes, book summaries. | `Movies/If_I_Stay.md` |
| **`Quotes/`** | Literary excerpts, notable quotes. | `Quotes/Aphorisms.md` |
| **`Limbo/`** | Uncategorized thoughts and fleeting ideas. | `Limbo/fleeting_thought.md` |

### 📌 Critical Hierarchy & Routing Rules:
1. **Never Dump Loose Notes into `Projects/` Root**:
   - **Incorrect**: `Projects/Revwr_v2_Canvas.md`
   - **Correct**: `Projects/Revwr v2/Canvas.md` (or `Projects/Revwr/Canvas.md`)
2. **Channel vs Project Routing**:
   - When asked to draft a canvas for a channel (like `#general`), route it to `General/General_Canvas.md`.
   - When asked to draft a canvas for a project (like `Revwr v2`), route it to `Projects/<Project Name>/<Topic>.md` (e.g. `Projects/Revwr v2/Canvas.md`).
3. **Automatic Directory Creation**: The Sympose runtime automatically creates nested project subfolders (e.g. `Projects/Revwr v2/`) on disk if they do not already exist.

---

## 3. 🕸️ Obsidian Wikilinks vs. Tags: Conceptual Distinction & Rules

In Obsidian, **Links** and **Tags** serve two fundamentally different architectural purposes. **Never conflate them:**

| Concept | Syntax | Purpose & Meaning in Obsidian | Examples |
| :--- | :--- | :--- | :--- |
| **Wikilinks** | `[[Target Note]]` | **Entities, Specific Notes & Concepts**: Points to concrete documents or knowledge graph nodes. Links build direct relationship edges between files. | `[[If I Stay]]`, `[[Anaïs Nin]]`, `[[Virginia]]`, `[[Sympose]]`, `[[Trading]]`, `[[2026-08-27]]` |
| **Tags** | `#tag` or `tags:` | **Taxonomy, State & Broad Categorization**: Classifies the type, status, or theme of a note across the vault without creating empty file nodes. | `#jour`, `#reflection`, `#wip`, `#architecture`, `#music`, `#growth` |

### 🚫 Critical Distinction Rules:
1. **NEVER Wrap Tags in Wikilinks**:
   - ❌ **Incorrect**: `[[jour]]`, `[[reflection]]`, `[[growth]]`, `[[self-compassion]]` *(This pollutes the graph by generating empty ghost file nodes for generic category words!)*
   - ✅ **Correct (Tags)**: `Tags: #jour #reflection #growth #music` (or YAML frontmatter `tags: [jour, reflection]`)
   - ✅ **Correct (Wikilinks)**: `[[If I Stay]]`, `[[Anaïs Nin]]`, `[[Virginia]]`, `[[Parting Time]]`, `[[2026-08-27]]`
2. **When to use Wikilinks (`[[...]]`)**:
   - People / Personas: `[[Anaïs Nin]]`, `[[Samantha]]`, `[[Virginia]]`, `[[Damiro]]`
   - Works / Media: `[[If I Stay]]`, `[[The Diary of Anaïs Nin]]`, `[[Parting Time]]`
   - Dedicated Concepts & Projects: `[[Sympose]]`, `[[Revwr]]`, `[[Zettelkasten]]`
   - Dates: `[[2026-08-27]]`
3. **When to use Tags (`#...`)**:
   - Classifiers: `#jour`, `#reflection`, `#summary`, `#decision`, `#wip`
   - Broad Themes: `#music`, `#cinema`, `#trading`, `#growth`, `#psychology`

---

## 4. 🏷️ Mandatory Tags & Frontmatter Taxonomy

Every entry and note written to Damiro's Obsidian vault **must include contextual tags** for Obsidian searchability, graph filtering, and tag browsing.

### A. Standalone Notes (`[WRITE_NOTE]`)
Always include relevant tags under `tags:` in the YAML frontmatter:
```yaml
---
entry: YYYY-MM-DD
created: YYYY-MM-DD HH:MM
type: note # or architectural-blueprint, guide, summary, canvas
tags:
  - general
  - canvas
  - ecosystem
  - sympose
---
```

### B. Daily Journal Entries (`[DAILY_NOTE]`)
Always include the primary tag `#jour` plus domain-specific tags at the bottom of the reflection payload:
- Primary tag: `#jour`
- Domain tags: `#reflection`, `#music`, `#cinema`, `#trading`, `#growth`, `#psychology`, `#philosophy`
- Example:
  ```markdown
  [DAILY_NOTE: Deep reflection with [[Anaïs Nin]] on [[Parting Time]] and memories of [[Lea]]. Explored grief, closure, and [[Personal Growth]].

  Tags: #jour #reflection #growth #music]
  ```

---

## 5. Delivery & Output Contract

1. **Conversational Efficiency (Zero Redundant Dumps)**:
   - When asked to draft or save a note/canvas to the vault, provide a **concise 2–3 sentence conversational summary** in your chat reply explaining the key themes or decisions.
   - **NEVER dump the entire 50-line markdown note into a code block in your chat message.** The full content belongs inside the `[WRITE_NOTE: ...]` or `[DAILY_NOTE: ...]` tag payload to be saved cleanly to disk.
2. **Pure Note Payloads (Zero Chat Commentary Inside Notes)**:
   - The content inside `[DAILY_NOTE: ...]` or `[WRITE_NOTE: ...]` must contain ONLY the actual journal entry or markdown note.
   - **NEVER include chat commentary, greeting boilerplate, or closing pleasantries** (e.g. *"Feel free to review and make adjustments"*, *"Let me know if you need anything else"*, *"This journal entry captures..."*) inside the note payload! Chat remarks belong in your Slack message, NEVER inside Damiro's Obsidian files.
3. **Emit the Action Tag Once at the Very End**: Place the single `[WRITE_NOTE: ...]` or `[DAILY_NOTE: ...]` tag at the bottom of your response.
4. **Single Clean Frontmatter**: The runtime preserves your YAML frontmatter cleanly. Do not repeat frontmatter blocks.
