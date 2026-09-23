"""Tests for sympose.engine.prompt — system-prompt assembly and message
shaping (docs/decisions/006)."""

from sympose.engine import prompt


def _grounding_result(title="Typography", rel_path="Typography.md", snippet="Some notes about fonts."):
    return {
        "file_name": "Typography.md",
        "rel_path": rel_path,
        "match_type": "title",
        "line_no": 1,
        "snippet": snippet,
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
