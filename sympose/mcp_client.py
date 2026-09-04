"""
Model Context Protocol (MCP) stdio JSON-RPC 2.0 Client.
"""

import os
import json
import logging
import subprocess
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from typing import Dict, List, Any, Optional, Tuple

log = logging.getLogger(__name__)


class MCPClient:
    """Standard-library JSON-RPC 2.0 stdio client for Model Context Protocol servers."""

    def __init__(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.name, self.command = name, command
        self.args = args or []
        self.custom_env = env or {}
        self.cwd = cwd or os.getcwd()
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()        # guards _request_id increments
        self._write_lock = threading.Lock()  # serialises stdin writes only
        # A background reader thread resolves each request's Future as its
        # response line arrives, keyed by JSON-RPC id — so concurrent requests
        # no longer block each other, and a response that arrives out of order
        # (or for someone else's request) is routed correctly instead of being
        # silently dropped by the old "read a line, discard if id mismatches" loop.
        self._pending: Dict[Any, "Future[Optional[Dict[str, Any]]]"] = {}
        self._pending_lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self.tools: List[Dict[str, Any]] = []
        self.is_connected = False

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _build_env(self) -> Dict[str, str]:
        full_env = os.environ.copy()
        import glob
        nvm_paths = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin")), reverse=True)
        paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"] + nvm_paths + [full_env.get("PATH", "")]
        full_env["PATH"] = ":".join([p for p in paths if p])
        for k, v in self.custom_env.items():
            if isinstance(v, str) and v.startswith("env:"):
                full_env[k] = os.getenv(v[4:].strip(), "")
            else:
                full_env[k] = str(v)
        return full_env

    def _drain_stderr(self) -> None:
        """Continuously drains the subprocess's stderr pipe into the debug log so a
        chatty MCP server can never fill the pipe buffer and deadlock the process."""
        if not self.process or not self.process.stderr:
            return
        try:
            for line in self.process.stderr:
                if line.strip():
                    log.debug("[MCP:%s stderr] %s", self.name, line.strip())
        except Exception:
            pass

    def _read_loop(self) -> None:
        """Background reader for the process lifetime: parses every stdout line and
        resolves the Future registered for its request id. Runs until stdout
        closes (process exited), at which point every still-pending request is
        resolved to None instead of being left to hang until its own timeout."""
        if self.process and self.process.stdout:
            try:
                for line in self.process.stdout:
                    clean = line.strip()
                    if not clean:
                        continue
                    try:
                        msg = json.loads(clean)
                    except Exception:
                        continue
                    if not isinstance(msg, dict) or msg.get("id") is None:
                        continue  # not a response to any pending request (e.g. a notification)
                    with self._pending_lock:
                        fut = self._pending.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(msg)
            except Exception:
                pass

        with self._pending_lock:
            leftover, self._pending = self._pending, {}
        for fut in leftover.values():
            if not fut.done():
                fut.set_result(None)

    def start(self) -> bool:
        if self.is_connected and self.process and self.process.poll() is None:
            return True
        try:
            import shutil
            cmd_bin = shutil.which(self.command, path=self._build_env().get("PATH")) or self.command
            self.process = subprocess.Popen(
                [cmd_bin] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self.cwd,
                env=self._build_env(),
            )
        except Exception as e:
            log.warning("Failed to spawn MCP server [%s]: %s", self.name, e)
            return False

        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "sympose", "version": "1.0.0"}},
        }
        resp = self._send_request(init_req)
        if not resp or "error" in resp:
            log.warning("MCP server [%s] initialization failed: %s", self.name, resp)
            self.stop()
            return False

        self._send_notification({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.is_connected = True
        self.tools = self.fetch_tools()
        return True

    def _send_notification(self, payload: Dict[str, Any]) -> None:
        if not self.process or self.process.poll() is not None or not self.process.stdin:
            return
        try:
            with self._write_lock:
                self.process.stdin.write(json.dumps(payload) + "\n")
                self.process.stdin.flush()
        except Exception:
            pass

    def _send_request(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Registers a Future for this request's id, writes it, and waits for the
        background reader thread (_read_loop) to resolve it. Concurrent calls no
        longer block each other — each gets its own Future regardless of arrival
        order or how many other requests are in flight."""
        if not self.process or self.process.poll() is not None or not self.process.stdin:
            return None
        req_id = payload.get("id")
        fut: "Future[Optional[Dict[str, Any]]]" = Future()
        with self._pending_lock:
            self._pending[req_id] = fut
        try:
            with self._write_lock:
                self.process.stdin.write(json.dumps(payload) + "\n")
                self.process.stdin.flush()
        except Exception:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            return None

        try:
            return fut.result(timeout=self.timeout)
        except FutureTimeoutError:
            return None
        finally:
            with self._pending_lock:
                self._pending.pop(req_id, None)

    def fetch_tools(self) -> List[Dict[str, Any]]:
        req = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {}}
        resp = self._send_request(req)
        if resp and "result" in resp and "tools" in resp["result"]:
            self.tools = resp["result"]["tools"]
            return self.tools
        return []

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if not self.is_connected and not self.start():
            return False, f"Failed to start MCP server [{self.name}]."

        req = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call", "params": {"name": tool_name, "arguments": arguments or {}}}
        resp = self._send_request(req)
        if not resp:
            return False, f"MCP server [{self.name}] timed out executing tool `{tool_name}`."
        if "error" in resp:
            err = resp["error"]
            return False, f"Tool error ({tool_name}): {err.get('message', str(err)) if isinstance(err, dict) else str(err)}"

        res = resp.get("result", {})
        text_outputs = []
        for item in res.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                text_outputs.append(item.get("text", ""))
            else:
                text_outputs.append(str(item))
        return (not bool(res.get("isError", False))), ("\n".join(text_outputs).strip() or "Tool executed with no output.")

    def get_litellm_tools(self) -> List[Dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            },
        } for t in self.tools]

    def stop(self) -> None:
        self.is_connected = False
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=2.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            finally:
                self.process = None
        # Defensive: _read_loop's own cleanup already resolves these once stdout
        # closes naturally, but don't leave any caller hanging on a manual stop().
        with self._pending_lock:
            leftover, self._pending = self._pending, {}
        for fut in leftover.values():
            if not fut.done():
                fut.set_result(None)
