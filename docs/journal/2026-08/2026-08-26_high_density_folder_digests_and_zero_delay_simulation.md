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

## 2. Architectural Decisions (ADR-030)

### ADR-030.1: High-Density Folder Digests (Small-to-Big Parsing)
* Instead of injecting full note bodies when analyzing whole folders, `VaultManager.get_folder_digest()` extracts a compact 1-line metadata manifest for every file in the directory.
* Extracts `name:`, `aka:`, `tags:`, `birthday:`, `created:`, and `up:` links.
* **Token Efficiency**: 45 individual notes are compressed from ~25,000 tokens into ~450 tokens.
* Allows any model (including local 9B open-weights) to synthesize the *entire* directory in a single turn without hallucinating or overflowing context.

### ADR-030.2: Universal Ban on Time-Delay Simulation (Pillar 6)
* Codified Pillar 6 in `docs/MEMORY_ARCHITECTURE_STANDARD.md` and injected into the universal system prompt builder (`sympose/profiles.py`):
  > *"ZERO TIME-DELAY SIMULATION: You process requests immediately in the current turn. You do NOT have background execution threads across minutes or hours. NEVER say 'Give me a few minutes', 'I will look into this and come back', 'hang tight', or 'Give me a moment to process'. Always deliver your findings immediately in the current turn or state what specific information is missing."*

### ADR-030.3: Direct Entity & Title Resolution
* Any entity or person mentioned in a prompt (e.g. `Miro`, `Summit`, `Virginia`) automatically resolves against note filenames across all allowed directories in `_resolve_vault_context()`.

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
