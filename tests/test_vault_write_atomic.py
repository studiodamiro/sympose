"""`write_atomic_text` (vault_write): the file is replaced whole or not at all."""

import os

import pytest

from sympose import vault_write


def test_it_writes_the_text_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "Note.md"
    vault_write.write_atomic_text(str(path), "hello\n")
    assert path.read_bytes() == b"hello\n"
    assert os.listdir(tmp_path) == ["Note.md"]


def test_it_replaces_existing_text(tmp_path):
    path = tmp_path / "Note.md"
    path.write_text("old and much longer text")
    vault_write.write_atomic_text(str(path), "new")
    assert path.read_bytes() == b"new"


def test_a_failed_replace_keeps_the_old_file_and_removes_the_temporary_one(tmp_path, monkeypatch):
    path = tmp_path / "Note.md"
    path.write_text("keep me")

    def refuse(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        vault_write.write_atomic_text(str(path), "replacement")
    assert path.read_text() == "keep me"
    assert os.listdir(tmp_path) == ["Note.md"]


def test_a_failed_write_keeps_the_old_file_and_removes_the_temporary_one(tmp_path):
    path = tmp_path / "Note.md"
    path.write_text("keep me")
    with pytest.raises(UnicodeEncodeError):
        vault_write.write_atomic_text(str(path), "lone surrogate \udc80")  # not encodable as utf-8
    assert path.read_text() == "keep me"
    assert os.listdir(tmp_path) == ["Note.md"]


def test_line_endings_are_kept_when_asked(tmp_path):
    path = tmp_path / "Note.md"
    vault_write.write_atomic_text(str(path), "one\r\ntwo\rthree\n", newline="")
    assert path.read_bytes() == b"one\r\ntwo\rthree\n"


def test_bytes_that_are_not_valid_utf8_survive_a_round_trip_with_surrogateescape(tmp_path):
    path = tmp_path / "Note.md"
    text = b"caf\xe9\n".decode("utf-8", errors="surrogateescape")
    vault_write.write_atomic_text(str(path), text, errors="surrogateescape")
    assert path.read_bytes() == b"caf\xe9\n"


def test_the_permissions_of_an_existing_file_are_kept(tmp_path):
    """A private note (0600) must not become readable by others because it was saved."""
    path = tmp_path / "Private.md"
    path.write_text("secret")
    os.chmod(path, 0o600)
    vault_write.write_atomic_text(str(path), "changed")
    assert path.read_text() == "changed"
    assert (path.stat().st_mode & 0o777) == 0o600


def test_a_new_file_gets_the_default_permissions_not_a_fixed_mode(tmp_path):
    path = tmp_path / "New.md"
    vault_write.write_atomic_text(str(path), "new")
    reference = tmp_path / "Reference.md"
    reference.write_text("x")  # created by open(): the umask-based default
    assert (path.stat().st_mode & 0o777) == (reference.stat().st_mode & 0o777)


def test_a_symlinked_note_is_written_through_and_stays_a_link(tmp_path):
    real = tmp_path / "Real.md"
    real.write_text("old")
    link = tmp_path / "Link.md"
    link.symlink_to(real)
    vault_write.write_atomic_text(str(link), "new")
    assert link.is_symlink()
    assert real.read_text() == "new"
