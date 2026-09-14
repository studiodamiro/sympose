"""
Unit tests for sympose.mcp.MCPRegistry — server-config discovery and the
active-client cache. MCPClient itself is stubbed (tested independently in
test_mcp_client.py) so these tests stay about the registry's own logic:
config file parsing, caching, reconnect-on-drop, and cleanup.
"""

import json

import pytest

from sympose.mcp import MCPRegistry


class _FakeClient:
    """Stands in for MCPClient — the registry only cares about is_connected,
    start(), and stop()."""

    def __init__(self, name, command, args=None, env=None, cwd=None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env
        self.cwd = cwd
        self.is_connected = False
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        self.is_connected = True
        return True

    def stop(self):
        self.stopped = True
        self.is_connected = False


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr("sympose.mcp.MCPClient", _FakeClient)
    return MCPRegistry(mcp_dir=str(tmp_path / "mcp"))


class TestAutoDiscover:
    def test_no_config_files_means_no_servers(self, registry):
        assert registry.servers == {}

    def test_loads_servers_json_mcp_servers_key(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "servers.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "Shell": {
                            "command": "shell-server",
                            "args": ["--stdio"],
                            "env": {"FOO": "bar"},
                        }
                    }
                }
            )
        )
        monkeypatch.setattr("sympose.mcp.MCPClient", _FakeClient)
        r = MCPRegistry(mcp_dir=str(mcp_dir))
        assert "shell" in r.servers  # lowercased
        assert r.servers["shell"]["command"] == "shell-server"
        assert r.servers["shell"]["args"] == ["--stdio"]
        assert r.servers["shell"]["env"] == {"FOO": "bar"}

    def test_loads_bare_servers_key(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "servers.json").write_text(
            json.dumps({"servers": {"git": {"command": "git-mcp"}}})
        )
        monkeypatch.setattr("sympose.mcp.MCPClient", _FakeClient)
        r = MCPRegistry(mcp_dir=str(mcp_dir))
        assert "git" in r.servers

    def test_entries_without_a_command_key_are_skipped(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "servers.json").write_text(
            json.dumps({"mcpServers": {"broken": {"args": ["x"]}}})
        )
        monkeypatch.setattr("sympose.mcp.MCPClient", _FakeClient)
        r = MCPRegistry(mcp_dir=str(mcp_dir))
        assert "broken" not in r.servers

    def test_malformed_json_is_ignored_not_raised(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "servers.json").write_text("{not valid json")
        monkeypatch.setattr("sympose.mcp.MCPClient", _FakeClient)
        r = MCPRegistry(mcp_dir=str(mcp_dir))  # must not raise
        assert r.servers == {}

    def test_prefers_servers_json_over_example(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "servers.json").write_text(
            json.dumps({"mcpServers": {"real": {"command": "real-cmd"}}})
        )
        (mcp_dir / "servers.json.example").write_text(
            json.dumps({"mcpServers": {"example": {"command": "example-cmd"}}})
        )
        monkeypatch.setattr("sympose.mcp.MCPClient", _FakeClient)
        r = MCPRegistry(mcp_dir=str(mcp_dir))
        assert "real" in r.servers
        assert "example" not in r.servers


class TestLoadFromConfig:
    def test_registers_servers_from_config_dict(self, registry):
        registry.load_from_config(
            {"mcp_servers": {"custom": {"command": "custom-cmd", "args": ["-v"]}}}
        )
        assert registry.servers["custom"]["command"] == "custom-cmd"

    def test_missing_mcp_servers_key_is_a_noop(self, registry):
        registry.load_from_config({})
        assert registry.servers == {}


class TestGetClient:
    def test_returns_none_for_an_unregistered_server(self, registry):
        assert registry.get_client("nope") is None

    def test_creates_and_caches_a_client(self, registry):
        # get_client() itself never connects the client (that's the caller's
        # job, e.g. workers.py's `if client and client.start(): ...`) — so
        # caching only kicks in once a client reports is_connected.
        registry.register_server("shell", "shell-server")
        c1 = registry.get_client("shell")
        assert isinstance(c1, _FakeClient)
        c1.is_connected = True
        c2 = registry.get_client("shell")
        assert c1 is c2  # cached, not re-created

    def test_lookup_is_case_insensitive(self, registry):
        registry.register_server("Shell", "shell-server")
        c1 = registry.get_client("SHELL")
        c1.is_connected = True
        assert registry.get_client("shell") is c1

    def test_recreates_client_once_previous_one_disconnected(self, registry):
        registry.register_server("shell", "shell-server")
        c1 = registry.get_client("shell")
        c1.is_connected = True
        assert registry.get_client("shell") is c1  # cached while connected

        c1.is_connected = False  # simulate the server process having died
        c2 = registry.get_client("shell")
        assert c2 is not c1


class TestShutdownAll:
    def test_stops_every_active_client_and_clears_the_cache(self, registry):
        registry.register_server("shell", "shell-server")
        registry.register_server("git", "git-server")
        c1 = registry.get_client("shell")
        c2 = registry.get_client("git")

        registry.shutdown_all()

        assert c1.stopped is True
        assert c2.stopped is True
        assert registry.active_clients == {}
