---
entry: 2026-08-26
created: 2026-08-26 02:15
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - memory/anti-hallucination
  - vault/digest
  - adr-030
---

# Engineering Journal: High-Density Folder Digests & Zero Time-Delay Simulation Standard

> **Date:** August 26, 2026  
> **Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Status:** APPROVED & IMPLEMENTED (ADR-030)  

---

## 1. Problem Statement & Autopsy

During Slack interactions with `@aurelius` (running `ollama/gemma2:9b`), the agent exhibited two critical failure modes when asked broad questions over directories with many files (e.g. `People/` containing 45 notes):

1. **The Fake Asynchronous "Sifting" Simulation**:
   The agent stated: *"Give me a few minutes to process all the information, and I'll come back with some findings that might surprise you!"* When the user messaged 3 minutes later (*"its been 3 minutes"*), the model generated generic filler (*"You have a lot of friends", "You use nicknames"*).
2. **Context Fragmentation**:
   Loading 45 full Markdown documents overflows the context window. However, loading only 4-5 full notes left 40 people completely invisible, leading the model to hallucinate placeholders like `[Name of Person]`.

---

## 2. Architectural Decisions

- **[ADR-030 — High-Density Folder Digests & Universal Ban on Time-Delay Simulation](./2026-08-26_adr-030-high-density-folder-digests-zero-delay.md):**
  `get_folder_digest()` emits a 1-line metadata manifest per file (45 notes:
  ~25,000 → ~450 tokens) (030.1); Pillar 6 bans "give me a few minutes"
  simulation (030.2); direct entity/title resolution against filenames (030.3).
  Rejected injecting full note bodies (overflow) and only the first few
  (invisibility).

---

## 3. Verification & Metrics

1. **High-Density Manifest Test**:
   * Scanned 45 notes in `People/`. Generated a clean 45-line manifest with names, birthdays, tags, and relations in **0.003s**.
2. **Direct Entity Match Test**:
   * Verified `"when is Miro's birthday??"` immediately injects `People/Miro.md` (`birthday: 2023-08-23`).
3. **LOC Compliance**:
   * `sympose/vault.py`: 182 LOC (<200 LOC ceiling).
   * `sympose/engine.py`: 200 LOC (<200 LOC ceiling).
   * `sympose/profiles.py`: 194 LOC (<200 LOC ceiling).
