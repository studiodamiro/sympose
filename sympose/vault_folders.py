"""
Folder-level vault operations: the high-density digest and random-sample
ground-truth extraction used by a folder-scoped turn, plus the
`has_vault_skill` gate. Folder/skill *discovery* (real subfolders,
chronological/daily-journal notes) lives in vault_folder_discovery.py — a
second-pass split of this same ADR-125 cluster, composed in below via
`FoldersMixin(DiscoveryMixin)` so vault.py's own class declaration doesn't
need to change.

Split out of vault.py per ADR-125 purely to keep that file under this
project's own size guidance; every method here is unchanged from its
prior home, so `VaultManager(FoldersMixin, ...)` is a pure move, not a
rewrite. Depends on `cls._get_master_vault`, `cls.get_allowed_dirs`, and
`cls._get_vault_snapshot`, all resolved normally through the MRO once
`VaultManager` inherits from this mixin, no parameter threading needed.
"""

import logging
import os
import re
from typing import Any

from sympose.config import config_manager, is_safe_path
from sympose.vault_folder_discovery import DiscoveryMixin

log = logging.getLogger(__name__)

# ADR-123.1: a folder-kind signal needs enough notes to trust a fraction -
# a 1- or 2-note folder showing "100% birthday" is noise, not signal.
_KIND_SIGNAL_MIN_NOTES = 3
# A field (or a single value within a field) only counts as "defining" once
# it covers this share of the folder's notes - "mostly", not "sometimes".
_KIND_SIGNAL_PRESENCE_THRESHOLD = 0.6
_KIND_SIGNAL_MAX_FIELDS = 3
# A field this common *everywhere* in the vault (e.g. every note gets a
# `created` timestamp by convention) tells you nothing distinctive about
# any one folder - confirmed against a real vault, not just theorized: a
# `Code/` and a `Projects/` folder both surfaced "created, title" before
# this existed, which doesn't actually distinguish either one. A field
# only counts as a signal once its presence *here* clears its own
# vault-wide presence by at least this many percentage points.
_KIND_SIGNAL_DISTINCTIVENESS_MARGIN = 0.25


def _normalize_field_tokens(value: Any) -> list[str]:
    """Normalizes one frontmatter field's raw value into lowercase string
    tokens, so a YAML list (`tags: [a, b]`), a comma-separated string
    (`tags: a, b`), and a plain scalar (`author: Damiro`) all feed the same
    value-clustering check the same way, regardless of which convention a
    given vault happens to use."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    if isinstance(value, str):
        if "," in value:
            return [t.strip().lower() for t in value.split(",") if t.strip()]
        v = value.strip()
        return [v.lower()] if v else []
    v = str(value).strip()
    return [v.lower()] if v else []


def _folder_kind_signal(
    entries: list[dict[str, Any]],
    vault_wide_entries: list[dict[str, Any]] | None = None,
) -> str:
    """ADR-123.1 — a structural, zero-configuration one-line hint about
    what kind of folder this is, derived purely from which frontmatter
    keys (and, where one value clearly dominates, which value) actually
    show up across most of these notes. No fixed vocabulary: every real
    YAML key any note in the folder actually uses is a candidate, not
    just a hand-picked list, so this works identically on any vault's own
    naming conventions - a vault that uses `status:` gets a signal built
    on `status`; one with almost no frontmatter gets silence, correctly.

    `vault_wide_entries` (optional - every note in the whole vault, same
    shape) lets a field's local presence be judged against how common it
    is *everywhere*, not just in isolation - confirmed necessary against
    a real vault, where `created`/`title` were common enough vault-wide
    that they surfaced for every folder without distinguishing any of
    them. Omit it (e.g. from a plain unit test) to skip that comparison
    and score on local presence alone.

    Silent (empty string) whenever nothing clears the bar: too few notes
    to trust a fraction, a field that isn't actually distinctive once
    weighed against the whole vault, or - the concentration-vs-catch-all
    case a real vault can have (e.g. a `Code/` folder where most notes
    share one dominant tag, next to a `Limbo/` catch-all where nothing
    repeats enough to dominate) - a folder that's genuinely a mix of
    unrelated notes gets no signal rather than a guessed one.

    Known, accepted limitation (see ADR-123's Consequences): this is a
    correlation, not semantic understanding, and a field that's present
    on most notes but whose values never repeat enough to dominate (e.g.
    `created` timestamps, which are expected to differ every note) still
    surfaces as a bare field name - still informative, just coarser than
    a value-level signal."""
    total = len(entries)
    if total < _KIND_SIGNAL_MIN_NOTES:
        return ""

    presence, value_counts, multi_valued = _tally_field_values(entries)
    baseline = _tally_field_values(vault_wide_entries) if vault_wide_entries else None
    baseline_total = len(vault_wide_entries) if vault_wide_entries else 0
    signals = _score_field_signals(
        presence, value_counts, multi_valued, total, baseline, baseline_total
    )
    if not signals:
        return ""
    signals.sort(key=lambda s: -s[0])
    top = [label for _, label in signals[:_KIND_SIGNAL_MAX_FIELDS]]
    return f"This folder's notes mostly carry: {', '.join(top)}."


def _tally_field_values(
    entries: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, dict[str, int]], set[str]]:
    """First pass over the folder's notes: how many notes carry each real
    frontmatter key (`presence`), how many notes carry each distinct
    normalized value per key (`value_counts`), and which keys were ever
    represented as a list or comma-separated value anywhere in the folder
    (`multi_valued`) - a YAML list is inherently how Obsidian expresses a
    multi-label, categorical field (`tags` being the obvious case), which
    `_score_field_signals` uses to tell "no dominant value, but presence
    alone is still meaningful" (e.g. `created`, always a single value)
    apart from "no dominant value means this is genuinely a mixed
    catch-all" (list-shaped fields whose values never cluster)."""
    presence: dict[str, int] = {}
    value_counts: dict[str, dict[str, int]] = {}
    multi_valued: set[str] = set()
    for entry in entries:
        meta = entry.get("meta")
        if not isinstance(meta, dict):
            continue
        # Keys are matched case-insensitively - real vaults accumulate
        # `title`/`Title` (or `created`/`Created`) inconsistency over time
        # (different tools, different eras of editing the same note), and
        # without this a genuinely near-universal field silently splits
        # into two halves that each fall under the presence threshold on
        # their own. `seen_this_note` stops a note that has *both*
        # casings of the same key from double-counting its own presence.
        seen_this_note: set[str] = set()
        for key, raw_value in meta.items():
            norm_key = str(key).lower()
            tokens = _normalize_field_tokens(raw_value)
            if not tokens:
                continue
            if isinstance(raw_value, list) or (
                isinstance(raw_value, str) and "," in raw_value
            ):
                multi_valued.add(norm_key)
            if norm_key not in seen_this_note:
                presence[norm_key] = presence.get(norm_key, 0) + 1
                seen_this_note.add(norm_key)
            counts = value_counts.setdefault(norm_key, {})
            # dict.fromkeys, not set(), so a tie in _score_field_signals'
            # max() deterministically favors whichever value was written
            # first, instead of an arbitrary hash-order pick.
            for tok in dict.fromkeys(tokens):
                counts[tok] = counts.get(tok, 0) + 1
    return presence, value_counts, multi_valued


def _is_distinctive(
    local_fraction: float,
    baseline_counts: dict[str, int] | None,
    baseline_key: str,
    baseline_total: int,
) -> bool:
    """True when `local_fraction` clears its own vault-wide baseline by
    the distinctiveness margin - or when there's no baseline to compare
    against at all (a plain unit test, or an empty vault), in which case
    local presence alone is trusted, same as before this existed."""
    if not baseline_counts or not baseline_total:
        return True
    baseline_fraction = baseline_counts.get(baseline_key, 0) / baseline_total
    return local_fraction - baseline_fraction >= _KIND_SIGNAL_DISTINCTIVENESS_MARGIN


def _score_field_signals(
    presence: dict[str, int],
    value_counts: dict[str, dict[str, int]],
    multi_valued: set[str],
    total: int,
    baseline: tuple[dict[str, int], dict[str, dict[str, int]], set[str]] | None,
    baseline_total: int,
) -> list[tuple[float, str]]:
    """Second pass: which fields clear the presence threshold, and for
    those, whether one value dominates strongly enough to name it directly
    (`"tags: code"`) rather than just the bare field name (`"created"`).
    A list-shaped field with no dominant value contributes no signal at
    all - a scattered `tags` list is a genuine catch-all, not a defining
    trait - while a scalar field like `created` still signals on presence
    alone, since its values are expected to differ every note. Either way,
    the field (or its dominant value) must also be distinctive against
    `baseline`, not just locally common - see `_is_distinctive`."""
    baseline_presence, baseline_value_counts, _ = baseline or ({}, {}, set())
    signals: list[tuple[float, str]] = []
    for key, count in presence.items():
        fraction = count / total
        if fraction < _KIND_SIGNAL_PRESENCE_THRESHOLD:
            continue
        dominant_value, dominant_count = max(
            value_counts[key].items(), key=lambda kv: kv[1]
        )
        dominant_fraction = dominant_count / total
        if dominant_fraction >= _KIND_SIGNAL_PRESENCE_THRESHOLD:
            if _is_distinctive(
                dominant_fraction,
                baseline_value_counts.get(key),
                dominant_value,
                baseline_total,
            ):
                signals.append((dominant_fraction, f"{key}: {dominant_value}"))
        elif key not in multi_valued and _is_distinctive(
            fraction, baseline_presence, key, baseline_total
        ):
            signals.append((fraction, key))
    return signals


class FoldersMixin(DiscoveryMixin):
    @classmethod
    def get_folder_digest(
        cls, profile: dict[str, Any], folder_name: str, max_files: int = 50
    ) -> str:
        """Extracts high-density 1-line metadata for all notes in a folder for comprehensive synthesis."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        target_dir = cls._resolve_named_folder_dir(allowed_dirs, folder_name)
        if not target_dir or not os.path.exists(target_dir):
            return f"Folder `{folder_name}` not found in allowed vault directories."

        snapshot_entries = cls._get_vault_snapshot(mv, [target_dir])[:max_files]
        kind_signal = _folder_kind_signal(
            snapshot_entries, cls._get_vault_snapshot(mv, [mv])
        )

        entries: list[str] = []
        for entry in snapshot_entries:
            fn, head = entry["file_name"], entry["full_content"][:1000]
            parts = []
            for k in (
                "name",
                "title",
                "aka",
                "tags",
                "birthday",
                "created",
                "up",
                "author",
            ):
                m = re.search(
                    rf"^{k}:\s*([^\n\r]+)", head, re.MULTILINE | re.IGNORECASE
                )
                if (
                    m
                    and m.group(1).strip()
                    and not m.group(1).strip().startswith(("-", "["))
                ):
                    parts.append(f"{k.capitalize()}: {m.group(1).strip()}")
                else:
                    sub = re.findall(
                        rf"^{k}:(?:\s*\n)((?:\s+-\s+[^\n]+\n)+)",
                        head,
                        re.MULTILINE | re.IGNORECASE,
                    )
                    if sub:
                        items = [
                            x.strip("- \t\n\"'") for x in sub[0].strip().split("\n")
                        ]
                        parts.append(f"{k.capitalize()}: {', '.join(items)}")
            fl = next(
                (
                    line.strip("# \t\r")
                    for line in head.split("\n")
                    if line.strip() and not line.startswith("---") and ":" not in line
                ),
                "",
            )
            summary = " | ".join(parts) if parts else fl[:80]
            entries.append(f"- `{fn}`: {summary}" if summary else f"- `{fn}`")

        if not entries:
            return f"No notes found in `{folder_name}/`."
        digest = (
            f"### High-Density Folder Digest (`{folder_name}/` - {len(entries)} notes):\n"
            + "\n".join(entries)
        )
        return f"{kind_signal}\n{digest}" if kind_signal else digest

    @classmethod
    def get_random_sample_notes(
        cls, profile: dict[str, Any], folder_name: str, count: int = 2
    ) -> str:
        """Extracts real note bodies from 1-3 randomly sampled notes in the folder so the model has true ground-truth content."""
        mv, allowed_dirs = cls._get_master_vault(), cls.get_allowed_dirs(profile)
        if not mv or not allowed_dirs:
            return "⚠️ Master notes directory not configured or access denied."
        target_dir = cls._resolve_named_folder_dir(allowed_dirs, folder_name)
        if not target_dir or not os.path.exists(target_dir):
            return ""
        valid_files = cls._collect_sample_candidate_files(target_dir)
        if not valid_files:
            return ""
        samples = cls._sample_and_read_notes(mv, valid_files, count)
        if not samples:
            return samples
        kind_signal = _folder_kind_signal(
            cls._get_vault_snapshot(mv, [target_dir]), cls._get_vault_snapshot(mv, [mv])
        )
        return f"{kind_signal}\n\n{samples}" if kind_signal else samples

    @classmethod
    def _resolve_named_folder_dir(
        cls, allowed_dirs: list[str], folder_name: str
    ) -> str | None:
        """Resolves `folder_name` to a real directory: an allowed dir whose
        own basename matches, or an immediate subfolder of one."""
        target_dir = next(
            (
                d
                for d in allowed_dirs
                if os.path.basename(d).lower() == folder_name.lower()
            ),
            None,
        )
        if not target_dir:
            for d in allowed_dirs:
                candidate = os.path.join(d, folder_name)
                if os.path.exists(candidate) and is_safe_path(candidate, d):
                    target_dir = candidate
                    break
        return target_dir

    @classmethod
    def _collect_sample_candidate_files(cls, target_dir: str) -> list[str]:
        """Every note file under `target_dir`, respecting
        `vault.ignore_folders`."""
        raw_ignore = config_manager.get("vault.ignore_folders")
        ignore_dirs = {str(d).lower().strip() for d in raw_ignore}
        valid_files = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in ignore_dirs and not d.startswith(".")
            ]
            for fn in files:
                if fn.endswith((".md", ".markdown", ".txt")):
                    valid_files.append(os.path.join(root, fn))
        return valid_files

    @classmethod
    def _sample_and_read_notes(
        cls, mv: str, valid_files: list[str], count: int
    ) -> str:
        """Randomly samples up to `count` files and reads their bodies as
        ground-truth payloads."""
        import random

        samples = random.sample(valid_files, min(count, len(valid_files)))
        payloads = []
        for fp in samples:
            rel = os.path.relpath(fp, mv)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read().strip()
                if body:
                    payloads.append(
                        f"### Ground-Truth Sandboxed Vault Note (`{rel}` - Exact Content):\n{body[:2500]}"
                    )
            except Exception as e:
                log.debug("Skipping sample note %s: %s", rel, e)
        return "\n\n---\n\n".join(payloads)

    @classmethod
    def has_vault_skill(cls, profile: dict[str, Any]) -> bool:
        """Verifies if the persona possesses the vault_read skill."""
        skills = profile.get("skills") or []
        return "vault_read" in skills

