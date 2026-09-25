"""The `sympose` command (docs/decisions/028)."""

import pytest

from sympose import launcher


@pytest.fixture
def ran(monkeypatch):
    calls = {}
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.update(web=kw))
    import sympose.cli.__main__ as cli_main

    monkeypatch.setattr(cli_main, "main", lambda: calls.update(cli=True))
    monkeypatch.delenv("PORT", raising=False)
    return calls


def test_with_no_command_it_lists_the_two(capsys):
    assert launcher.main([]) == 0

    out = capsys.readouterr().out
    assert "cli" in out and "web" in out and "usage: sympose" in out


def test_help_lists_them_and_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["-h"])

    assert stop.value.code == 0 and "terminal" in capsys.readouterr().out


def test_an_unknown_command_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["dashboard"])

    assert stop.value.code == 2


def test_cli_starts_the_terminal_chat(ran):
    assert launcher.main(["cli"]) == 0
    assert ran == {"cli": True}


def test_web_serves_on_this_machine_only_on_port_8000_by_default(ran, capsys):
    assert launcher.main(["web"]) == 0

    assert ran["web"] == {"host": "127.0.0.1", "port": 8000}
    assert "http://127.0.0.1:8000" in capsys.readouterr().out


def test_web_takes_its_port_from_the_flag_before_the_environment(ran, monkeypatch, capsys):
    monkeypatch.setenv("PORT", "9100")
    launcher.main(["web"])
    assert ran["web"]["port"] == 9100

    launcher.main(["web", "--port", "9200"])
    assert ran["web"]["port"] == 9200
    assert "http://127.0.0.1:9200" in capsys.readouterr().out


def test_web_has_no_way_to_listen_beyond_this_machine(ran, capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["web", "--host", "0.0.0.0"])

    assert stop.value.code == 2 and "host" not in ran


def test_a_port_that_is_not_a_number_is_said_plainly(ran, monkeypatch, capsys):
    monkeypatch.setenv("PORT", "eight")

    assert launcher.main(["web"]) == 1
    assert "PORT must be a number" in capsys.readouterr().err and "web" not in ran


def test_web_without_a_built_app_says_so_and_does_not_start(ran, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sympose.web_static.WEBUI_DIR", str(tmp_path))

    assert launcher.main(["web"]) == 1
    assert "no built web app" in capsys.readouterr().err and "web" not in ran


def test_web_mounts_the_app_after_the_api_so_the_api_wins(ran, monkeypatch):
    import uvicorn

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app))
    launcher.main(["web"])

    paths = [getattr(route, "path", "") for route in seen["app"].routes]
    assert paths.index("/health") < paths.index("/{path:path}")
    assert paths.index("/api/vaults") < paths.index("/{path:path}")
    assert paths[-1] == "/{path:path}"


def test_the_console_script_and_the_shipped_files_are_declared():
    import tomllib

    with open("pyproject.toml", "rb") as f:
        project = tomllib.load(f)

    assert project["project"]["scripts"] == {"sympose": "sympose.launcher:main"}
    data = project["tool"]["setuptools"]["package-data"]["sympose"]
    assert "webui/*" in data and "webui/assets/*" in data and "reference/*.md" in data


def test_only_this_machines_own_names_may_address_the_web_server(ran, monkeypatch):
    import uvicorn
    from fastapi.testclient import TestClient

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app))
    launcher.main(["web"])
    client = TestClient(seen["app"])

    for host in ("127.0.0.1:8000", "localhost:8000", "localhost", "127.0.0.1"):
        assert client.get("/health", headers={"host": host}).status_code == 200
    for host in ("evil.example", "evil.example:8000", "localhost.evil.example", "127.0.0.1.evil.example", "testserver"):
        assert client.get("/health", headers={"host": host}).status_code == 400
        assert client.get("/", headers={"host": host}).status_code == 400
