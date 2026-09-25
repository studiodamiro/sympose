"""Tests must not depend on whether an embedding model is running on the machine (docs/decisions/027).
The shipped default of `grounding_search` is `auto`, which would call one, so every test starts with the
default set to `keywords` and with a settings file of its own (the maintainer's real `settings.json` is
never read). A test of meaning-based search sets its mode itself; a test of the shipped default is marked
`@pytest.mark.shipped_defaults`."""

import pytest

from sympose.engine import embeddings


def pytest_configure(config):
    config.addinivalue_line("markers", "shipped_defaults: run with the settings defaults the product ships")


@pytest.fixture(autouse=True)
def _keyword_search_by_default(request, tmp_path_factory, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path_factory.mktemp("settings") / "settings.json"))
    if request.node.get_closest_marker("shipped_defaults") is None:
        monkeypatch.setattr(embeddings, "DEFAULT_MODE", embeddings.KEYWORDS)
