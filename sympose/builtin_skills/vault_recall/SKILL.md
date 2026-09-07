---
name: "vault_recall"
title: "Obsidian Vault Historical Synthesis & Recall"
description: "Tiered retrieval protocol to locate, inspect, and synthesize historical notes, decisions, and daily reflections from the Obsidian vault using local-first heuristics."
recommended_models:
  - "gemini/gemini-3.5-flash-lite"
  - "ollama/qwen2.5:14b"
  - "ollama/gemma2:9b"
tags:
  - memory
  - retrieval
  - obsidian
  - history
---

# 📚 Obsidian Vault Historical Recall Protocol

> **The Ground-Truth Sovereignty Axiom:**  
> **Your Markdown documents on disk are the sovereign single source of truth. AI models are mere transient cognitive assistants.** The model owns zero memory outside of actual files and must never fabricate past events, simulate retrieval actions, or invent fictional notes.

---

## 1. Zero-Hallucination Grounding Directives

1. **Strict Verbatim Fidelity**: When the user requests a note or past reflection, quote the exact written text verbatim (`> Quote`) from the document payload.
2. **Candid Ignorance Over Pleasant Fabrication**: If a date, project, or topic has no matching note on disk, state candidly: *"I have no record of that in your vault."* Never invent plausible dates or generic diary summaries.
3. **No Action Simulation**: Never emit roleplay markers (`*[Begins retrieval]*`, `*Outputs text*`). Deliver real text payloads or concrete findings directly.

---

## 2. Dynamic Vault Discovery (Tier 0 Discovery)

1. **Structure & Hierarchy Agnosticism**:
   - **Never assume rigid folder names or fixed hierarchies.** Users organize vaults differently (Flat, PARA, Johnny Decimal, Zettelkasten, or Date-nested).
   - Discover matching files dynamically using non-destructive inspection (`find`, `ls`, path pattern matching).
   - Locate relevant notes through multi-dimensional anchors:
      - **Topic & Entity Keywords**: In filenames (e.g. `*tadhana*`, `*database*`, `*theology*`).
      - **Chronological / Date Formats**: Any date schema (`YYYY-MM-DD`, `YYYY/MM/DD`, `YYYYMMDD`, etc.).
      - **Frontmatter & Metadata**: YAML keys (`tags:`, `type:`, `project:`, `category:`).
      - **Wikilink & Backlink Traversal**: Follow internal wikilinks (`[[Note Title]]`) and reverse backlinks (incoming references) to discover connected ideas across projects and daily logs.
2. **Backlink & Graph Inversion**:
    - When exploring a concept, entity, or person (e.g. `[[Virginia]]`, `[[FastAPI]]`, `[[Sympose]]`), query incoming references to gather every journal entry, architectural doc, and meeting log referencing that node.
3. **System Noise & Binary Exclusion**:
    - Strictly ignore hidden dot-directories (`.*`, `.obsidian/`, `.git/`, `.trash/`) and binary asset directories (`Attachments/`, images, PDFs).

---

## 3. Small-to-Big Anchor Parsing (Tier 1 Extraction)

Do not ingest full unstructured transcripts when targeted sections are available:
1. **YAML Frontmatter**: Extract `entry:`, `type:`, `project:`, `agent:`, `tags:`.
2. **High-Signal Headings**: Focus extraction on:
   - `## Key Decisions` / `## Architecture Highlights`
   - `## Action Items & Next Steps`
   - `### Reflection (HH:MM)`
3. **Isolate Top Matches**: Narrow down the search to the **2–4 most relevant notes** before generating the final synthesis.

---

## 4. Context-Adaptive Output Modes

Deliver findings dynamically based on the specific goal of the inquiry—**do NOT force an artificial "Historical Timeline" template when simple note retrieval was requested**:

### Mode A: Direct Note Retrieval (Single Note Inspection)
When asked to pull up, inspect, or present a specific note:
- Quote the verbatim Markdown content directly with primary source metadata (Path, Created/Updated date).
- Do not append empty or irrelevant "Timeline" headings.

### Mode B: Multi-Note Historical Synthesis & Timeline
When investigating a multi-month initiative, milestone evolution, or decision history across multiple notes:
```markdown
### 🗓️ Historical Synthesis: [Topic / Project Name]

#### Primary Sources:
- `Projects/SampleProject/TECH_DEBT.md` (2026-08-20)
- `Daily/2026/08-August/2026-08-15.md` (2026-08-15)

#### Key Decisions & Chronology:
1. **[Decision 1]**: Summary of what was agreed upon and why.
2. **[Decision 2]**: Specific architectural choice or constraint identified.
```

### Mode C: Targeted Fact / Snippet Lookup
When answering a specific factual question from notes (e.g. *"what was the database port?"*):
- Deliver the direct answer and exact quotation immediately without boilerplate wrapper headings.
