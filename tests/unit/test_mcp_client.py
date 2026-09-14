"""
Unit tests for sympose.mcp_client.MCPClient — the stdio JSON-RPC 2.0 client
that talks to MCP servers. Real subprocesses aren't spawned; instead a fake
Popen double drives the same request/response mechanics an actual server
would (queue-backed stdout, a handler that answers each JSON-RPC method),
so the client's real threading/Future/id-routing code runs unmodified —
only the OS process boundary is faked.
"""

import queue
import threading

import pytest

from sympose.mcp_client import MCPClient


class _FakeStderr:
    def __iter__(self):
        return iter(())


class _FakeProcess:
    """Stands in for subprocess.Popen. Writes to .stdin are parsed as JSON-RPC
    and handed to `handler`; whatever `handler` returns (if anything) is
    queued for the background reader thread to pick up off .stdout — the
    same way a real server's response line would arrive."""

    def __init__(self, handler):
        self._handler = handler
        self._out: queue.Queue = queue.Queue()
        self._alive = True
        self.stdin = self
        self.stdout = self
        self.stderr = _FakeStderr()

    # -- stdin --
    def write(self, data: str) -> None:
        import json

        line = data.strip()
        if not line:
            return
        msg = json.loads(line)
        resp = self._handler(msg)
        if resp is not None:
            self._out.put(json.dumps(resp) + "\n")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    # -- stdout: blocks until a response is queued, ends on terminate/kill --
    def __iter__(self):
        while True:
            item = self._out.get()
            if item is None:
                return
            yield item

    # -- process lifecycle --
    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self._alive = False
        self._out.put(None)

    def kill(self):
        self._alive = False
        self._out.put(None)

    def wait(self, timeout=None):
        return 0


def _echo_handler(msg):
    method = msg.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg["id"], "result": {"capabilities": {}}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echoes input",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                        },
                    }
                ]
            },
        }
    if method == "tools/call":
        params = msg.get("params", {})
        if params.get("name") == "echo":
            text = (params.get("arguments") or {}).get("text", "")
            return {
                "jsonrpc": "2.0",
                "id": msg["id"],
                "result": {"content": [{"type": "text", "text": f"echo: {text}"}]},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "isError": True,
                "content": [{"type": "text", "text": "unknown tool"}],
            },
        }
    return None


def _install_fake_popen(monkeypatch, handler):
    fake = _FakeProcess(handler)
    monkeypatch.setattr("sympose.mcp_client.subprocess.Popen", lambda *a, **k: fake)
    return fake


@pytest.fixture
def client(monkeypatch):
    _install_fake_popen(monkeypatch, _echo_handler)
    return MCPClient(name="echo-server", command="fake-cmd", timeout=2.0)


class TestStart:
    def test_connects_and_fetches_tools_on_success(self, client):
        assert client.start() is True
        assert client.is_connected is True
        assert [t["name"] for t in client.tools] == ["echo"]

    def test_returns_false_when_initialize_reports_error(self, monkeypatch):
        def handler(msg):
            if msg.get("method") == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "error": {"message": "bad handshake"},
                }
            return None

        _install_fake_popen(monkeypatch, handler)
        c = MCPClient(name="broken", command="fake-cmd", timeout=2.0)
        assert c.start() is False
        assert c.is_connected is False

    def test_returns_false_when_server_never_responds(self, monkeypatch):
        _install_fake_popen(monkeypatch, lambda msg: None)
        c = MCPClient(name="silent", command="fake-cmd", timeout=0.2)
        assert c.start() is False
        assert c.is_connected is False

    def test_returns_false_when_spawn_raises(self, monkeypatch):
        def _raise(*a, **k):
            raise OSError("no such command")

        monkeypatch.setattr("sympose.mcp_client.subprocess.Popen", _raise)
        c = MCPClient(name="missing", command="does-not-exist")
        assert c.start() is False

    def test_second_call_is_a_noop_once_connected(self, monkeypatch):
        spawn_count = {"n": 0}
        fake = _FakeProcess(_echo_handler)

        def counting_popen(*a, **k):
            spawn_count["n"] += 1
            return fake

        monkeypatch.setattr("sympose.mcp_client.subprocess.Popen", counting_popen)
        c = MCPClient(name="echo-server", command="fake-cmd", timeout=2.0)

        assert c.start() is True
        assert c.start() is True
        assert spawn_count["n"] == 1


class TestCallTool:
    def test_success_returns_text_content(self, client):
        client.start()
        ok, text = client.call_tool("echo", {"text": "hi"})
        assert ok is True
        assert text == "echo: hi"

    def test_server_reported_error_surfaces_as_failure(self, client):
        client.start()
        ok, text = client.call_tool("nonexistent_tool", {})
        assert ok is False
        assert "unknown tool" in text

    def test_json_rpc_error_object_surfaces_as_failure(self, monkeypatch):
        def handler(msg):
            if msg.get("method") == "initialize":
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {}}
            if msg.get("method") == "tools/list":
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": []}}
            if msg.get("method") == "tools/call":
                return {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "error": {"message": "boom"},
                }
            return None

        _install_fake_popen(monkeypatch, handler)
        c = MCPClient(name="erroring", command="fake-cmd", timeout=2.0)
        c.start()
        ok, text = c.call_tool("whatever", {})
        assert ok is False
        assert "boom" in text

    def test_times_out_when_server_stops_responding_mid_call(self, monkeypatch):
        def handler(msg):
            if msg.get("method") == "initialize":
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {}}
            if msg.get("method") == "tools/list":
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": []}}
            return None  # tools/call gets no reply

        _install_fake_popen(monkeypatch, handler)
        c = MCPClient(name="hangs", command="fake-cmd", timeout=0.2)
        c.start()
        ok, text = c.call_tool("echo", {"text": "hi"})
        assert ok is False
        assert "timed out" in text

    def test_auto_starts_when_not_yet_connected(self, client):
        assert client.is_connected is False
        ok, text = client.call_tool("echo", {"text": "auto"})
        assert ok is True
        assert text == "echo: auto"
        assert client.is_connected is True

    def test_two_concurrent_calls_each_get_their_own_response(self, client):
        """Regression coverage for the id-routing fix: two requests in flight
        at once must each resolve to their own response, not whichever
        arrives first for both."""
        client.start()
        results = {}

        def _call(key, text):
            results[key] = client.call_tool("echo", {"text": text})

        t1 = threading.Thread(target=_call, args=("a", "first"))
        t2 = threading.Thread(target=_call, args=("b", "second"))
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        assert results["a"] == (True, "echo: first")
        assert results["b"] == (True, "echo: second")


class TestGetLitellmTools:
    def test_shape_matches_litellm_function_schema(self, client):
        client.start()
        tools = client.get_litellm_tools()
        assert tools == [
            {
                "type": "function",
                "function": {
                    "name": "echo",
                    "description": "Echoes input",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                    },
                },
            }
        ]

    def test_empty_before_any_tools_fetched(self, monkeypatch):
        _install_fake_popen(monkeypatch, _echo_handler)
        c = MCPClient(name="fresh", command="fake-cmd")
        assert c.get_litellm_tools() == []


class TestStop:
    def test_disconnects_and_clears_process(self, client):
        client.start()
        client.stop()
        assert client.is_connected is False
        assert client.process is None

    def test_resolves_any_pending_request_instead_of_hanging(self, monkeypatch):
        # A call in flight when stop() is invoked must not hang forever.
        def handler(msg):
            if msg.get("method") == "initialize":
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {}}
            if msg.get("method") == "tools/list":
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": []}}
            return None  # tools/call never answered

        fake = _install_fake_popen(monkeypatch, handler)
        c = MCPClient(name="stoppable", command="fake-cmd", timeout=5.0)
        c.start()

        result = {}

        def _call():
            result["r"] = c.call_tool("echo", {"text": "x"})

        import time

        t = threading.Thread(target=_call)
        t.start()
        time.sleep(0.1)  # let the request actually register as pending
        c.stop()
        t.join(timeout=2)

        assert result["r"][0] is False
        assert fake.poll() == 0
