"""Reading the `.env` file of the folder Sympose runs in (docs/decisions/, issue #74)."""

import os

import pytest

from sympose import envfile

NAME = "SYMPOSE_TEST_ENVFILE_VALUE"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv(NAME, "unset")  # so whatever `load_env` writes is removed again after the test
    monkeypatch.delenv(NAME)


def test_it_reads_the_env_file_of_the_working_folder(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"{NAME}=from-here\n")
    monkeypatch.chdir(tmp_path)

    envfile.load_env()

    assert os.environ[NAME] == "from-here"


def test_it_does_not_search_the_folders_above(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"{NAME}=from-above\n")
    below = tmp_path / "a" / "b"
    below.mkdir(parents=True)
    monkeypatch.chdir(below)

    envfile.load_env()

    assert NAME not in os.environ


def test_a_variable_that_is_already_set_wins(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"{NAME}=from-file\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(NAME, "from-shell")

    envfile.load_env()

    assert os.environ[NAME] == "from-shell"


def test_a_folder_with_no_env_file_is_fine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    envfile.load_env()  # must not raise

    assert NAME not in os.environ
