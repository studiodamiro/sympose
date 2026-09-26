"""Creating a new note or folder (`vault_write_create`): where it lands, what it starts with, and what is refused.

It must never overwrite an existing file and never write outside the persona's folders. Everything runs
in a temporary vault."""

import datetime
import os

import pytest

from sympose import vault_write_create as create
from sympose.vault_snapshot import parse_frontmatter
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

ALL = {"vault_folders": ["*"]}
CODE = {"vault_folders": ["Code"]}
NOW = datetime.datetime(2026, 3, 4, 9, 5).astimezone()


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return str(root)


def write(vault, rel, text="x"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def read(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8") as f:
        return f.read()


# --- templates ------------------------------------------------------------------------------


def test_no_templates_folder_means_no_template(vault):
    assert create.get_template_for_path(vault, "Projects/Plan.md") is None
    assert create.get_template_for_path("", "Plan.md") is None


def test_a_folders_own_template_is_found_by_singular_or_plural_ignoring_case(vault):
    write(vault, "Templates/Project template.md", "PROJECT")
    write(vault, "Templates/Note template.md", "NOTE")
    for folder in ("Projects", "project", "PROJECTS"):
        assert create.get_template_for_path(vault, f"{folder}/Plan.md") == "PROJECT"


def test_a_plural_template_serves_a_singular_folder(vault):
    write(vault, "Templates/Meetings template.md", "MEETING")
    assert create.get_template_for_path(vault, "Meeting/Standup.md") == "MEETING"


def test_a_folder_without_a_template_and_a_top_level_note_get_the_general_one(vault):
    write(vault, "Templates/Project template.md", "PROJECT")
    write(vault, "Templates/Note template.md", "NOTE")
    assert create.get_template_for_path(vault, "Journal/Day.md") == "NOTE"
    assert create.get_template_for_path(vault, "Loose.md") == "NOTE"


def test_files_that_are_not_templates_are_not_used(vault):
    write(vault, "Templates/Journal.md", "NOT A TEMPLATE")
    assert create.get_template_for_path(vault, "Journal/Day.md") is None


def test_the_general_template_is_not_taken_for_a_folder_called_note(vault):
    write(vault, "Templates/Note template.md", "NOTE")
    write(vault, "Templates/Idea template.md", "IDEA")
    assert create.get_template_for_path(vault, "Idea/One.md") == "IDEA"
    assert create.get_template_for_path(vault, "Note/One.md") == "NOTE"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a file with no permissions")
def test_an_unreadable_template_is_no_template(vault):
    path = write(vault, "Templates/Note template.md", "NOTE")
    os.chmod(path, 0)
    try:
        assert create.get_template_for_path(vault, "Loose.md") is None
    finally:
        os.chmod(path, 0o644)


def test_template_placeholders_are_filled_in_and_the_result_is_trimmed():
    out = create._render_template("\n---\nt: {{title}}\nd: {{date}} {{time}} {{date:YYYY}}\n---\n", "My Note", NOW)
    assert out == "---\nt: My Note\nd: 2026-03-04 09:05 2026\n---"


# --- create_note ----------------------------------------------------------------------------


def test_a_new_note_starts_with_a_title_stub_made_from_its_file_name(vault):
    result = create.create_note(ALL, "Folder/my_new-note")
    assert result == f"Created note: `{os.path.join('Folder', 'my_new-note.md')}`"
    text = read(vault, "Folder/my_new-note.md")
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "My New Note"
    assert meta["tags"] == []
    assert str(meta["created"]) == datetime.date.today().isoformat()
    assert body == "\n# My New Note\n\n"


def test_the_stub_is_used_when_the_template_is_not_frontmatter(vault):
    write(vault, "Templates/Note template.md", "just a checklist")
    create.create_note(ALL, "Idea")
    assert parse_frontmatter(read(vault, "Idea.md"))[0]["title"] == "Idea"


def test_a_folders_template_seeds_the_new_note(vault):
    write(vault, "Templates/Project template.md", "---\ntitle: {{title}}\nstatus: new\n---")
    create.create_note(ALL, "Projects/big_plan")
    meta, body = parse_frontmatter(read(vault, "Projects/big_plan.md"))
    assert meta == {"title": "Big Plan", "status": "new"}
    assert body == "\n# Big Plan\n\n"


def test_given_content_is_written_as_it_is_with_one_final_newline(vault):
    create.create_note(ALL, "a", "no newline")
    create.create_note(ALL, "b", "one newline\n")
    create.create_note(ALL, "c", "")
    assert (read(vault, "a.md"), read(vault, "b.md"), read(vault, "c.md")) == ("no newline\n", "one newline\n", "\n")


def test_a_note_is_never_overwritten(vault):
    write(vault, "Keep.md", "original")
    assert create.create_note(ALL, "Keep", "replacement") == NOTE_EXISTS
    assert read(vault, "Keep.md") == "original"


def test_a_folder_with_the_note_name_also_counts_as_existing(vault):
    os.makedirs(os.path.join(vault, "Odd.md"))
    assert create.create_note(ALL, "Odd") == NOTE_EXISTS


def test_the_name_is_cleaned_and_the_extension_is_added_once(vault):
    for given in ('"Quoted"', "'Single'", "  Spaced  ", "/Lead/ing", "\\Back", "Already.md"):
        assert create.create_note(ALL, given).startswith("Created note")
    assert sorted(os.listdir(vault)) == ["Already.md", "Back.md", "Lead", "Quoted.md", "Single.md", "Spaced.md"]


@pytest.mark.parametrize("name", ["", "   ", "'", "/", "\\\\"])
def test_a_blank_name_is_refused(vault, name):
    assert create.create_note(ALL, name) == NOTE_DENIED
    assert os.listdir(vault) == []


@pytest.mark.parametrize("name", ["../Escape", "Sub/../../Escape", "A/../../../etc/x"])
def test_a_name_that_leaves_the_vault_is_refused(vault, tmp_path, name):
    assert create.create_note(ALL, name) == NOTE_DENIED
    assert os.listdir(tmp_path) == ["vault"]


def test_a_bare_name_goes_to_the_personas_first_folder_and_a_path_is_taken_from_the_vault_root(vault):
    create.create_note(CODE, "Bare")
    assert create.create_note(CODE, "Code/Sub/Deep").startswith("Created note")
    assert os.path.exists(os.path.join(vault, "Code", "Bare.md"))
    assert os.path.exists(os.path.join(vault, "Code", "Sub", "Deep.md"))


def test_a_restricted_persona_cannot_create_outside_its_folders(vault):
    assert create.create_note(CODE, "Private/Secret") == NOTE_DENIED
    assert not os.path.exists(os.path.join(vault, "Private"))


def test_no_vault_configured_is_refused(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    assert create.create_note(ALL, "Anything") == NOTE_DENIED


def test_a_failed_write_reports_the_error_and_leaves_no_note(vault, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(create, "write_atomic_text", refuse)
    assert create.create_note(ALL, "Nope").startswith("Error: Failed to create note")
    assert not os.path.exists(os.path.join(vault, "Nope.md"))


@pytest.mark.parametrize("title", ["Meeting #3", "Yes", "2024", "Null", 'Say "Hi" Now', "A: B", "Café: 日本"])  # `.title()` writes "Null"
def test_the_generated_title_reads_back_as_the_same_text(vault, title):
    create.create_note(ALL, title)
    assert parse_frontmatter(read(vault, f"{title}.md"))[0]["title"] == title


def test_the_generated_title_is_written_readably_in_the_file(vault):
    create.create_note(ALL, "Café 日本")

    assert 'title: "Café 日本"\n' in read(vault, "Café 日本.md")  # quoted, and not as \\u escapes


# --- create_folder --------------------------------------------------------------------------


def test_a_new_folder_is_created_empty_including_its_parents(vault):
    assert create.create_folder(ALL, "A/B/C") == f"Created folder: `{os.path.join('A', 'B', 'C')}`"
    assert os.listdir(os.path.join(vault, "A", "B", "C")) == []


def test_an_existing_folder_or_file_is_never_replaced(vault):
    os.makedirs(os.path.join(vault, "Have"))
    write(vault, "File", "data")
    assert create.create_folder(ALL, "Have") == NOTE_EXISTS
    assert create.create_folder(ALL, "File") == NOTE_EXISTS
    assert read(vault, "File") == "data"


def fail_makedirs_for(monkeypatch, name, error):
    """Make `os.makedirs` fail for one folder only: the sandbox lookup uses it too."""
    real = os.makedirs

    def makedirs(path, *args, **kwargs):
        if str(path).endswith(name):
            raise error
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "makedirs", makedirs)


def test_a_folder_created_by_someone_else_in_the_meantime_is_reported_as_existing(vault, monkeypatch):
    fail_makedirs_for(monkeypatch, "Race", FileExistsError("Race"))
    assert create.create_folder(ALL, "Race") == NOTE_EXISTS


def test_a_folder_that_cannot_be_created_reports_the_error(vault, monkeypatch):
    fail_makedirs_for(monkeypatch, "Nope", PermissionError("read-only"))
    assert create.create_folder(ALL, "Nope").startswith("Error: Failed to create folder")


def test_a_folder_name_is_cleaned_of_quotes_and_outer_slashes(vault):
    for given in ('"Quoted"', "/Lead/ing", "Trail/", "\\Back"):
        assert create.create_folder(ALL, given).startswith("Created folder")
    assert sorted(os.listdir(vault)) == ["Back", "Lead", "Quoted", "Trail"]
    assert os.path.isdir(os.path.join(vault, "Lead", "ing"))


@pytest.mark.parametrize("name", ["", "  ", "/", "'/'"])
def test_a_blank_folder_name_is_refused(vault, name):
    assert create.create_folder(ALL, name) == NOTE_DENIED


def test_a_folder_name_that_leaves_the_vault_is_refused(vault, tmp_path):
    assert create.create_folder(ALL, "../Escape") == NOTE_DENIED
    assert os.listdir(tmp_path) == ["vault"]


def test_a_restricted_persona_makes_bare_folders_in_its_own_folder_and_none_outside(vault):
    assert create.create_folder(CODE, "Mine").startswith("Created folder")
    assert os.path.isdir(os.path.join(vault, "Code", "Mine"))
    assert create.create_folder(CODE, "Private/Theirs") == NOTE_DENIED
    assert not os.path.exists(os.path.join(vault, "Private"))
