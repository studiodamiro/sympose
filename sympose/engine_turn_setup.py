"""
Resolving a chat turn's inputs before the model is ever called: persisting
a natural-language "remember that X" ask, and assembling the system prompt
(persona base + vault context + a matched working-memory nudge + a due
ritual pull + a session-recall digest).

Split out of engine_turn_pipeline.py per ADR-125's own note that that
cluster would need a second pass once it was out of engine.py and easier
to judge; every method here is unchanged from its prior home. Resolving
this turn's vault_ctx (the module's original third concern) split out
again into `engine_turn_vault_context.py` once this file crossed the
project's own <200 LOC ceiling on its own.
`TurnPipelineMixin(TurnSetupMixin, ...)` in engine_turn_pipeline.py
composes this in, so engine.py's own class declaration doesn't need to
change. Depends on `self.pm`, `self._lock`, `self.active_ritual`, plus
sibling methods from `GroundingHelpersMixin` (`_ritual_pull_due`,
`_is_full_body_vault_ctx`, `_build_session_history_digest`), all resolved
normally through the MRO.
"""

import re
from typing import Any

from sympose.profiles import ProfileManager
from sympose.session_recall import has_session_recall_intent
from sympose.vault import VaultManager


class TurnSetupMixin:
    def _maybe_persist_remembered_fact(
        self, handle: str, profile: dict[str, Any], clean_input: str
    ) -> str:
        """If `clean_input` is a natural-language "remember that X" ask (and
        not a slash command), persists X to persona memory and returns the
        confirmation line to show the user; '' when it isn't one."""
        nat_match = re.search(
            r"^(?:(?:hey|hi|hello)?\s*(?:@?\w+[,:]?\s*)?)?(?:please\s+)?remember\s+(?:that\s+|to\s+|:\s+)?(.+)$",
            clean_input,
            re.IGNORECASE,
        )
        if nat_match and not clean_input.startswith("/"):
            extracted_fact = nat_match.group(1).strip()
            if extracted_fact:
                self.pm.append_memory(handle, extracted_fact)
                return f"> 🧠 **Persisted to {profile.get('name', handle)}'s memory:** *{extracted_fact}*\n\n"
        return ""

    def _build_turn_system_prompt(
        self,
        handle: str,
        profile: dict[str, Any],
        vault_ctx: str | None,
        h_key: str,
        clean_input: str,
        curr_session_id: str,
        is_fresh: bool,
    ) -> tuple[str, str | None, bool]:
        """Assembles this turn's system prompt: the persona's base prompt
        plus this turn's vault_ctx, a matched working-memory nudge, a fresh
        random-pull when an active ritual is due, and a session-recall
        digest when asked for one. May return an updated vault_ctx — a
        ritual pull fetches new content this turn, which also flips
        `is_fresh` to True: a ritual pull is itself a new-this-turn note
        introduction, same as `_resolve_turn_vault_context`'s
        (engine_turn_vault_context.py) own structural-match case. Returns
        (system_prompt, vault_ctx, is_fresh)."""
        system_prompt = self.pm.build_system_prompt(profile)
        if vault_ctx:
            system_prompt += f"\n\n{vault_ctx}"
        # Deterministic, zero-round-trip nudge: persona memory is dumped in
        # full inside build_system_prompt's cached block, but a small model
        # can still fail to notice one relevant bullet among everything
        # else there. Appended per-turn (not baked into the cached prefix
        # above) so it doesn't defeat local prompt-caching the way a
        # per-turn timestamp would.
        mem_hit = ProfileManager.find_relevant_memory_fact(
            self.pm.get_persona_memory(profile), clean_input
        )
        if mem_hit:
            system_prompt += (
                "\n\n### Matched Working-Memory Fact (This Turn)\n"
                "The user's message closely overlaps this fact you already "
                f"have - it is very likely what they mean:\n- {mem_hit}"
            )
        # The matched fact (or an already-engaged ritual carried over from a
        # prior turn - see _ritual_pull_due) may describe a "pull a random
        # note" ritual by whatever name the user gave it. Nothing in
        # resolve_turn_context's own phrase-matching fires for a message
        # like "let's play our favorite game" or its own follow-up "let's
        # do another one" - neither ever asks for a random note in those
        # words - so without this, a real note is never actually fetched
        # and the model fills the gap with a plausible-sounding invented
        # title ("Echoes of August" in a live incident). Respects the same
        # vault-skill gate resolve_turn_context itself enforces.
        #
        # Live bug: a *thin* vault_ctx carried over from an earlier,
        # unrelated turn (a search-results digest, not a full note) was
        # enough to skip this entirely - "already have something" - even
        # though it has nothing to do with this turn's request and isn't
        # strong enough for the citation-mismatch safety net to engage
        # either (that only activates on a full note body), so the model's
        # fabrication sailed through completely unchecked. Only a genuine
        # full-body context (this turn's own structural match, or a
        # freshly refreshed single-note carry-over) counts as "already have
        # something" here; a thin digest gets superseded by a real pull.
        if self._ritual_pull_due(
            mem_hit, self.active_ritual.get(h_key, False), clean_input
        ) and not self._is_full_body_vault_ctx(
            vault_ctx
        ) and VaultManager.has_vault_skill(profile):
            fresh_pull = VaultManager.resolve_ritual_random_pull(profile, clean_input)
            if fresh_pull:
                vault_ctx = fresh_pull
                is_fresh = True
                with self._lock:
                    self.active_vault_ctx[h_key] = vault_ctx
                    self.active_ritual[h_key] = True
                system_prompt += f"\n\n{vault_ctx}"
        if has_session_recall_intent(clean_input):
            system_prompt += "\n\n" + self._build_session_history_digest(
                handle, curr_session_id
            )
        return system_prompt, vault_ctx, is_fresh
