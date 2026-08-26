---
entry: 2026-08-26
created: 2026-08-26 14:48
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - grounding
  - epistemic-humility
  - adr-035
---

# Engineering Journal: Evidence-Based Grounding & Epistemic Humility Standard (ADR-035)

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace Hopper / Samantha  
> **Status:** APPROVED & IMPLEMENTED (ADR-035)  

---

## 1. Context & Motivation

A recurring pathology in conversational LLMs is **"Eager Assumption Bias"**: when presented with ambiguous pronouns (*"is this appropriate?"*, *"what do you think of that layout?"*), models often jump to conclusions by pulling arbitrary recent memory files (e.g. past projects like Revwr v2) and generating unsolicited blueprints instead of asking for clarification.

In high-reliability engineering, **guessing without evidence is unacceptable**. You are not expecting too much—you are upholding the core tenet of intelligent assistance: **First-Principles, Evidence-Based Reasoning**.

---

## 2. Architectural Decisions (ADR-035)

### ADR-035.1: The "No Evidence = No Assumptions" Mandate
* When an input lacks explicit antecedent data or refers to an ambiguous subject (*"this"*, *"that"*, *"the thread"*), agents are strictly forbidden from guessing or assuming context from working memory.
* Agents must **pause and ask clarifying questions** before executing or generating plans.

### ADR-035.2: Channel & Thread Boundary Awareness
* Agents acknowledge that they only have live visibility into the active conversation thread.
* If a user asks about an external channel (e.g. `#general`) or another thread, the agent must not fabricate or guess the contents—it must explicitly request the snippet or context.

### ADR-035.3: Universal Soul & Rule Injection
* Injected into all agent profiles:
  * [`profiles/samantha_soul.md`](file:///Users/damiro/Development/sympose/profiles/samantha_soul.md)
  * [`profiles/grace_soul.md`](file:///Users/damiro/Development/sympose/profiles/grace_soul.md)
  * [`profiles/aurelius_soul.md`](file:///Users/damiro/Development/sympose/profiles/aurelius_soul.md)
  * [`.agents/rules/identity.md`](file:///Users/damiro/Development/sympose/.agents/rules/identity.md)

---

## 3. Verification & Example

```text
User: "You think this is appropriate for #general thread here on slack?"
Agent (Correct Behavior): "What specific message, design, or layout are you referring to by 'this'? Paste it over and I'll give you a grounded assessment for #general."
```
