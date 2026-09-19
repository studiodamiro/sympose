"""
Resolving this turn's vault_ctx: a fresh structural match, a dropped stale
context when the message is itself a new vault ask, or a refreshed re-read
of a carried-over single-note reference.

Split out of engine_turn_setup.py (itself an ADR-125 split of
engine_turn_pipeline.py) once that module crossed this project's own
<200 LOC ceiling — this is the "resolving this turn's vault_ctx" third of
that module's own docstring, on its own now that it grew past a single
combined file's budget. `TurnPipelineMixin` (engine_turn_pipeline.py)
composes this in alongside `TurnSetupMixin`, so `engine.py`'s own class
declaration doesn't need to change. Depends on `self._lock`,
`self.active_vault_ctx`, `self.active_ritual`, and `PersonaEngine` itself
(`_get_history_key`), all resolved normally through the MRO.
"""

from typing import Any

from sympose.vault import VaultManager


class TurnVaultContextMixin:
    @staticmethod
    def _is_incidental_recall_keyword_hit(
        has_intent: bool, subject: str, had_leadin: bool
    ) -> bool:
        """True when `has_intent` fires only because a bare
        `vault.search_triggers` word (e.g. "note", "vault", "folder")
        appears somewhere in the message — no recall lead-in phrase
        consumed, no subject extracted either. `extract_recall_subject`
        already requires a lead-in and a subject to agree before returning
        `had_leadin=True`, so this is the residual case: a trigger word
        coincidentally present in an otherwise ordinary sentence, not a
        genuine, subject-bearing vault ask. Takes the already-derived
        `VaultManager.recall_signal` values rather than the raw message -
        `_resolve_turn_vault_context` below computes that once per turn and
        reuses it here and in its own `has_intent` branch, instead of each
        site re-running the same subject/lead-in extraction."""
        return has_intent and not had_leadin and not subject

    def _refresh_active_note(self, profile: dict[str, Any], h_key: str) -> str | None:
        """Re-reads a carried-over single-note `vault_ctx` fresh from disk
        (rather than replaying a frozen copy that may no longer match the
        file) and updates `active_vault_ctx` to match. Shared by the
        incidental-keyword carve-out and the plain carry-over-reuse branch
        in `_resolve_turn_vault_context` below - both hit this identical
        recovery, just via different trigger conditions, so it isn't
        duplicated in both `elif` bodies."""
        vault_ctx = VaultManager.refresh_note_context(
            profile, self.active_vault_ctx[h_key]
        )
        self.active_vault_ctx[h_key] = vault_ctx
        return vault_ctx

    def _resolve_turn_vault_context(
        self,
        handle: str,
        session_id: str | None,
        profile: dict[str, Any],
        clean_input: str,
    ) -> tuple[str | None, str, bool]:
        """Resolves this turn's vault_ctx: a fresh structural match, a
        dropped stale context when the message is itself a new vault ask,
        or a refreshed re-read of a carried-over single-note reference.
        Returns (vault_ctx, h_key, is_fresh) — `is_fresh` is True only for a
        genuine new-this-turn structural match, never for a re-read of a
        note already on the table. Consumed by `_vault_ctx_title_missing`
        (engine_grounding.py) so that check only holds a reply to
        "name the note's title" on the turn that actually introduces it —
        see that method's own docstring for the live over-firing bug this
        distinction fixes."""
        h_key = self._get_history_key(handle, session_id)
        # Retrieval itself stays outside the lock — it's the hot-path I/O this
        # session's caching work was aimed at, and must not serialize concurrent
        # chats across personas/threads behind one engine-wide lock.
        vault_ctx = VaultManager.resolve_turn_context(profile, clean_input)
        is_fresh = bool(vault_ctx)
        with self._lock:
            if vault_ctx:
                self.active_vault_ctx[h_key] = vault_ctx
                return vault_ctx, h_key, is_fresh
            # `recall_signal` computed once here and reused by both branches
            # below - each used to independently re-run the same subject/
            # lead-in extraction (`_is_incidental_recall_keyword_hit`'s own
            # internal call, then this `elif`'s own `has_recall_intent`
            # call), tripling the same regex work on this hot path for no
            # behavioral gain when a fresh structural match wasn't found.
            has_intent, subject, had_leadin = VaultManager.recall_signal(
                clean_input
            )
            if (
                self._is_incidental_recall_keyword_hit(has_intent, subject, had_leadin)
                and self.active_vault_ctx.get(h_key)
                and not self.active_ritual.get(h_key)
            ):
                # Live bug (2026-09-19): "so, what can you say about that
                # note?" matched has_recall_intent purely because "note" is
                # a configured vault.search_triggers word — no recall
                # lead-in, no extractable subject, just a trigger word that
                # happens to appear in an ordinary follow-up about the note
                # already carried from the prior turn. Confirmed live: this
                # wiped a real, already-fetched Ideaverse.md digest, leaving
                # the model nothing to work with and forcing a blind
                # sub-agent guess that landed on an unrelated note. Treat an
                # incidental keyword hit (no lead-in, no subject) the same
                # as the carry-over refresh below instead of the wipe case
                # right after it — a genuine subject-bearing ask (a real
                # lead-in, or any extracted subject) still wipes as before.
                vault_ctx = self._refresh_active_note(profile, h_key)
            elif has_intent:
                # Fresh vault question, nothing retrieved: drop any carried-over
                # context so the model can't answer "pull up X" from a stale,
                # unrelated note. It must take the honest path (spawn a sub-agent
                # or say it has no record). A distinct, explicit vault ask like
                # this also ends any random-pull ritual in progress — it's a
                # new topic, not "another one" of the same game.
                self.active_vault_ctx[h_key] = None
                self.active_ritual[h_key] = False
            elif self.active_vault_ctx.get(h_key) and not self.active_ritual.get(
                h_key
            ):
                # Reusing a prior turn's resolved context — re-read a
                # single-note reference fresh rather than replaying a frozen
                # copy that may no longer match the file on disk. Skipped
                # while a random-pull ritual is active: re-serving the same
                # note here would satisfy the ritual block's own full-body
                # check below before it gets a chance to run, silently
                # turning "let's do another one" into "here's that same one
                # again" instead of a fresh pull.
                vault_ctx = self._refresh_active_note(profile, h_key)
        return vault_ctx, h_key, is_fresh
