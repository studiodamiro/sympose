"""
Model Context Protocol (MCP) stdio JSON-RPC 2.0 Client.
"""

import os
import json
import subprocess
import threading
import time
from typing import Dict, List, Any, Optional, Tuple


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
        self._lock = threading.Lock()
        self.tools: List[Dict[str, Any]] = []
        self.is_connected = False

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _build_env(self) -> Dict[str, str]:
        full_env = os.environ.copy()
        paths = ["/opt/homebrew/bin", "/usr/local/bin", os.path.expanduser("~/.nvm/versions/node"), full_env.get("PATH", "")]
        full_env["PATH"] = ":".join([p for p in paths if p])
        for k, v in self.custom_env.items():
            if isinstance(v, str) and v.startswith("env:"):
                full_env[k] = os.getenv(v[4:].strip(), "")
            else:
                full_env[k] = str(v)
        return full_env

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
            print(f"⚠️ Failed to spawn MCP server [{self.name}]: {e}")
            return False

        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "sympose", "version": "1.0.0"}},
        }
        resp = self._send_request(init_req)
        if not resp or "error" in resp:
            print(f"⚠️ MCP server [{self.name}] initialization failed: {resp}")
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
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()
        except Exception:
            pass

    def _send_request(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.process or self.process.poll() is not None or not self.process.stdin or not self.process.stdout:
            return None
        req_id = payload.get("id")
        try:
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()
        except Exception:
            return None

        start_time = time.time()
        while time.time() - start_time < self.timeout:
            line = self.process.stdout.readline()
            if not line:
                if self.process.poll() is not None:
                    break
                time.sleep(0.01)
                continue
            clean = line.strip()
            if not clean:
                continue
            try:
                msg = json.loads(clean)
                if isinstance(msg, dict) and msg.get("id") == req_id:
                    return msg
            except Exception:
                continue
        return None

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
