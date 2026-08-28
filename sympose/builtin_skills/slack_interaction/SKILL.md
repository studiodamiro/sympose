---
name: "slack_interaction"
title: "Slack Integration & Conversation Protocol"
description: "Master protocols for Slack Socket Mode: thread lifecycle, thread deletion & reset commands, silence protocols, dynamic @mentions, and multi-agent interaction etiquette."
tags:
  - slack
  - conversation
  - thread-management
  - silence-protocol
  - multi-agent
---

# 💬 Slack Interaction & Conversation Protocol

This skill codifies how Sympose agents interact within Slack channels, private DMs, and threaded conversations.

---

## 1. Thread Lifecycles & Deletion Commands

Sympose maintains isolated memory per Slack thread (`channel_id:thread_ts`).

### 🧹 Conversation Wiping & Thread Reset
When the user wants to clear or reset a thread's history, they may use phrases such as:
* `"delete this thread"`, `"clear conversation"`, `"wipe chat"`, `"purge history"`, `"/clear"`, `"/reset"`
* **Silent Mode (`do not reply` / `no acknowledge` / `silent`)**:
  - If the user specifies silence (e.g., *"delete this thread, do not reply"* or *"wipe chat, stay quiet"*), the daemon wipes memory in RAM, attempts to delete past bot messages, places a `🧹` reaction on the message, and **emits ZERO text**.
* **Standard Clear**:
  - If silence is not requested, the daemon confirms with `🧹 Conversation history deleted for @<persona>.` and cleans up the thread state.

---

## 2. The Silence & No-Spam Protocol

* **Respecting "Do Not Reply" / Silence**: If the user instructs you not to respond or when a prompt is purely an acknowledgment, do NOT generate boilerplate text like `"(No response)"`, `"(silence)"`, or `"*acknowledged your message*"`.
* Simply emit an expressive reaction (e.g. `[REACT: white_check_mark]` or `[REACT: broom]`) and output no message text.

---

## 3. Direct Messages & 1-on-1 Threads

* **Zero Tag Sign-Offs**: Never append `@user` or any persona handle as an ending signature or suffix. Speak directly and naturally to the user.
* **No Spontaneous Peer Tagging in DMs**: Do **NOT** tag other agents inside private DMs unless the user explicitly asks you to bring them into the conversation.

---

## 4. Multi-Agent Channels & Group Threads

* **Clickable Native Tags**: When referring to other agents or the primary user in shared channels, write natural `@mentions` (e.g. `@<handle>`, `@<user>`). Sympose dynamically formats them into native highlighted Slack pills (`<@USER_ID>`).
* **Zero Scripted Roleplay**: Never write fake dialogue scripts or headers for other bots (e.g. `**Peer:** ...`). Speak strictly for yourself in your own turn.
* **Tag & Ask in Group Threads**: When collaboration is active in a shared channel, state your own perspective and explicitly `@mention` the other agent with a direct question so they can answer for themselves.
* **Master Moderation & Anti-Spam**: Prevent scope creep in group discussions. Keep exchanges focused, timebox to 1–2 quick turns, synthesize recommendations, and hand the flow back cleanly.

---

## 5. Slack Emotion & Reaction Autonomy

* Use `[REACT: <emoji_name>]` (e.g., `[REACT: eyes]`, `[REACT: rocket]`, `[REACT: rose]`, `[REACT: bulb]`, `[REACT: sparkles]`, `[REACT: fire]`) to add authentic emoji reactions to incoming messages.
* Reactions communicate presence, emotional resonance, celebration, or strategic alignment without cluttering the chat thread. Use them naturally.
