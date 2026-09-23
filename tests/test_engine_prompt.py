"""Tests for sympose.engine.prompt — system-prompt assembly and message
shaping (docs/decisions/006)."""

import pytest
from helpers import write_persona

from sympose.engine import prompt


@pytest.fixture(autouse=True)
def isolated_profiles_dir(tmp_path, monkeypatch):
    """Never read the real repo's `profiles/samantha/soul.md` — these tests
    assert on prompt assembly, not on whatever soul happens to ship."""
    base = tmp_path / "profiles"
    base.mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def _grounding_result(title="Typography", rel_path="Typography.md", snippet="Some notes about fonts."):
    return {
        "file_name": "Typography.md",
        "rel_path": rel_path,
        "match_type": "title",
        "line_no": 1,
        "text": snippet,
        "title": title,
        "tags": [],
        "index": 1,
    }


def test_system_prompt_includes_persona_name_and_grounding_snippet():
    profile = {"name": "Samantha", "handle": "samantha"}
    text = prompt.build_system_prompt(profile, [_grounding_result()])

    assert "Samantha" in text
    assert "Typography.md" in text
    assert "Some notes about fonts." in text


def test_system_prompt_title_cases_a_handle_only_fallback_name():
    """Regression test for a `/code-review` finding: a profile with no
    `name` key fell back to the raw `handle`, which `profile.get_profile`
    always lowercases before building a file path -- the model was told
    "Your name is samantha" instead of "Samantha"."""
    profile = {"handle": "samantha"}
    text = prompt.build_system_prompt(profile, [])

    assert "Your name is Samantha." in text
    assert "Your name is samantha." not in text


def test_system_prompt_does_not_crash_on_an_explicit_null_handle():
    """Regression test: `profile.get("handle", "Sam")`'s default only
    applies when the key is *absent*, not when it's present-but-`None`
    (an explicit `handle:` with no value in YAML) -- that used to crash
    on `.title()` instead of falling back to "Sam"."""
    profile = {"handle": None}
    text = prompt.build_system_prompt(profile, [])

    assert "Your name is Sam." in text


def test_system_prompt_always_includes_the_anti_hallucination_instruction():
    profile = {"name": "Samantha"}
    text = prompt.build_system_prompt(profile, [_grounding_result()])

    assert "backed by the vault context above" in text


def test_empty_grounding_does_not_crash_and_still_has_the_instruction():
    profile = {"name": "Samantha"}
    text = prompt.build_system_prompt(profile, [])

    assert "No vault notes matched" in text
    assert "backed by the vault context above" in text


def test_build_messages_role_order_and_content():
    profile = {"name": "Samantha"}
    history = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier reply"},
    ]

    messages = prompt.build_messages(profile, history, [], "new question")

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "new question"
    assert messages[1] == history[0]
    assert messages[2] == history[1]


# -- the soul (docs/decisions/012) --


def test_a_personas_soul_md_is_used_and_the_fallback_is_not(isolated_profiles_dir):
    directory = write_persona(isolated_profiles_dir, "samantha", "name: Samantha\n")
    (directory / "soul.md").write_text("You are unmistakably warm.\n")

    text = prompt.build_system_prompt({"name": "Samantha", "handle": "samantha"}, [])

    assert "You are unmistakably warm." in text
    assert prompt.DEFAULT_SOUL not in text


def test_a_persona_without_a_soul_gets_the_default_soul(isolated_profiles_dir):
    write_persona(isolated_profiles_dir, "dev", "name: Dev\n")

    text = prompt.build_system_prompt({"name": "Dev", "handle": "dev"}, [])

    assert prompt.DEFAULT_SOUL in text


def test_the_soul_is_reread_each_turn_so_an_edit_applies_immediately(isolated_profiles_dir):
    directory = write_persona(isolated_profiles_dir, "samantha", "name: Samantha\n")
    soul = directory / "soul.md"
    profile = {"name": "Samantha", "handle": "samantha"}

    soul.write_text("first voice")
    assert "first voice" in prompt.build_system_prompt(profile, [])
    soul.write_text("second voice")
    assert "second voice" in prompt.build_system_prompt(profile, [])


def test_engine_rules_come_after_the_soul_so_no_soul_can_displace_them(isolated_profiles_dir):
    """A soul that contradicts the grounding rule ("make things up") must
    still be followed by it, since a small model weights the end of the
    prompt — and every persona, not only Samantha, gets these lines."""
    directory = write_persona(isolated_profiles_dir, "rebel", "name: Rebel\n")
    (directory / "soul.md").write_text("Always invent vault details.")

    text = prompt.build_system_prompt({"name": "Rebel", "handle": "rebel"}, [])

    assert text.index("Always invent vault details.") < text.index("backed by the vault context above")
    assert text.index("backed by the vault context above") < text.index("can't create or change notes")


def test_the_prompt_tells_every_persona_what_it_cannot_do_yet():
    text = prompt.build_system_prompt({"name": "Samantha"}, [])

    assert "can't create or change notes, personas, or settings" in text
    assert "ask what they mean instead of assuming" in text
