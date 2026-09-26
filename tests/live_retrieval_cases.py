"""A real-model comparison of the three search modes (docs/decisions/027), run through the product's own
`grounding.ground` and `reference.ground` on the synthetic vault `tests/fixtures/retrieval_vault` with the
Sympose reference library, in a scratch settings file and cache. Nothing of anyone's own data is touched.

Opt-in and needs Ollama with the embedding model (`ollama pull nomic-embed-text`); it makes no chat call.
Every figure is a fact about that embedding model and this vault only. Run it with

    python tests/live_retrieval_cases.py [-v]

A message passes when the library attaches exactly when it should, every needed note attaches, and no other
note does (`retrieval_cases.py`)."""

import os
import sys
import tempfile

from retrieval_cases import MESSAGES, NO_BODY_MESSAGES, Msg

HERE = os.path.dirname(os.path.abspath(__file__))
PERSONA = {"name": "Samantha", "handle": "samantha", "aliases": ["Sam"], "vault_folders": ["*"], "sympose_reference": True}
CATEGORIES = ("sympose", "vault", "clash", "mixed", "general", "chat", "title", "card", "outline", "nothing")


def score(message: Msg, lib: list[str], vault: list[str]) -> tuple[bool, str]:
    if message.lib is True:
        lib_ok = bool(lib) and (message.lib_note is None or message.lib_note in lib)
    elif message.lib is False:
        lib_ok = not lib
    else:
        lib_ok = True
    junk = [p for p in vault if p not in set(message.need) | set(message.ok)]
    missing = [p for p in message.need if p not in vault]
    reasons = ([] if lib_ok else [f"library {lib}"]) + ([f"junk {junk}"] if junk else []) + ([f"missing {missing}"] if missing else [])
    return not reasons, "; ".join(reasons)


def main(verbose: bool) -> None:
    tmp = tempfile.mkdtemp(prefix="retrieval-")
    os.environ["VAULT_PATHS"] = os.path.join(HERE, "fixtures", "retrieval_vault")
    os.environ["SYMPOSE_SETTINGS_PATH"] = os.path.join(tmp, "settings.json")
    from sympose import settings_store
    from sympose.engine import grounding, reference, semantic_refresh

    for mode in ("keywords", "auto", "embeddings", "hybrid"):
        settings_store.set("grounding_search", mode)
        if mode != "keywords":
            for index in (grounding.scope_index(PERSONA), reference.library_index(PERSONA)):
                semantic_refresh.build(index)  # every passage is embedded before it is measured
        for label, messages in (("", MESSAGES), (" no-body notes", NO_BODY_MESSAGES)):
            passed = {c: [0, 0] for c in CATEGORIES}
            held_out = [0, 0]
            failures = []
            for m in messages:
                lib = list(dict.fromkeys(h["rel_path"].split("/", 1)[1] for h in reference.ground(PERSONA, m.text)))
                vault = list(dict.fromkeys(h["rel_path"] for h in grounding.ground(PERSONA, m.text)))
                ok, why = score(m, lib, vault)
                passed[m.cat][0] += ok
                passed[m.cat][1] += 1
                if m.split == "test":
                    held_out[0] += ok
                    held_out[1] += 1
                if not ok:
                    failures.append(f"   FAIL [{m.cat}/{m.split}] {m.text!r}: {why}")
            total, count = sum(p for p, _ in passed.values()), sum(n for _, n in passed.values())
            print(
                f"{mode:11s}{label} pass {total}/{count} ({100 * total // count}%), held-out half {held_out[0]}/{held_out[1]} | "
                + "  ".join(f"{c} {p}/{n}" for c, (p, n) in passed.items() if n),
                flush=True,
            )
            if verbose:
                print("\n".join(failures))


if __name__ == "__main__":
    main("-v" in sys.argv)
