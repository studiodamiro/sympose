"""
Model Context Protocol (MCP) Client & Bridge for Sympose.
Provides lightweight JSON-RPC 2.0 stdio client capabilities for community and local MCP servers.
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
        self.name = name
        self.command = command
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
        """Resolves system environment and expands 'env:VAR_NAME' placeholders."""
        full_env = os.environ.copy()
        for k, v in self.custom_env.items():
            if isinstance(v, str) and v.startswith("env:"):
                var_name = v[4:].strip()
                full_env[k] = os.getenv(var_name, "")
            else:
                full_env[k] = str(v)
        return full_env

    def start(self) -> bool:
        """Spawns the MCP server subprocess and completes the initialization handshake."""
        if self.is_connected and self.process and self.process.poll() is None:
            return True

        cmd = [self.command] + self.args
        try:
            self.process = subprocess.Popen(
                cmd,
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

        # 1. Send initialize request
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sympose", "version": "1.0.0"},
            },
        }

        resp = self._send_request(init_req)
        if not resp or "error" in resp:
            print(f"⚠️ MCP server [{self.name}] initialization failed: {resp}")
            self.stop()
            return False

        # 2. Send initialized notification
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        self._send_notification(init_notif)

        # 3. Fetch available tools
        self.is_connected = True
        self.tools = self.fetch_tools()
        return True

    def _send_notification(self, payload: Dict[str, Any]) -> None:
        """Writes a notification to server stdin without expecting a response."""
        if not self.process or self.process.poll() is not None or not self.process.stdin:
            return
        try:
            json_str = json.dumps(payload) + "\n"
            self.process.stdin.write(json_str)
            self.process.stdin.flush()
        except Exception as e:
            print(f"⚠️ Error sending notification to [{self.name}]: {e}")

    def _send_request(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sends a JSON-RPC request and synchronously reads the response with a timeout."""
        if not self.process or self.process.poll() is not None or not self.process.stdin or not self.process.stdout:
            return None

        req_id = payload.get("id")
        try:
            json_str = json.dumps(payload) + "\n"
            self.process.stdin.write(json_str)
            self.process.stdin.flush()
        except Exception as e:
            print(f"⚠️ Error writing to [{self.name}] stdin: {e}")
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
        """Queries the MCP server for available tools via tools/list."""
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        }
        resp = self._send_request(req)
        if resp and "result" in resp and "tools" in resp["result"]:
            self.tools = resp["result"]["tools"]
            return self.tools
        return []

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Executes a specific tool via tools/call and returns (success, text_result)."""
        if not self.is_connected and not self.start():
            return False, f"Failed to start MCP server [{self.name}]."

        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        resp = self._send_request(req)
        if not resp:
            return False, f"MCP server [{self.name}] timed out executing tool `{tool_name}`."

        if "error" in resp:
            err = resp["error"]
            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return False, f"Tool error ({tool_name}): {err_msg}"

        res = resp.get("result", {})
        is_error = bool(res.get("isError", False))

        content_list = res.get("content", [])
        text_outputs = []
        for item in content_list:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_outputs.append(item.get("text", ""))
                elif item.get("type") == "image":
                    text_outputs.append("[Image data omitted]")
                else:
                    text_outputs.append(str(item))
            else:
                text_outputs.append(str(item))

        output_str = "\n".join(text_outputs).strip() or "Tool executed with no output."
        return (not is_error), output_str

    def get_litellm_tools(self) -> List[Dict[str, Any]]:
        """Converts MCP tool definitions into OpenAI/LiteLLM function schemas."""
        converted = []
        for t in self.tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            })
        return converted

    def stop(self) -> None:
        """Gracefully terminates the MCP subprocess."""
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


class MCPRegistry:
    """Manages available MCP server configurations and connection instances."""

    def __init__(self):
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.active_clients: Dict[str, MCPClient] = {}

    def register_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> None:
        """Registers an MCP server definition."""
        self.servers[name.lower()] = {
            "name": name.lower(),
            "command": command,
            "args": args or [],
            "env": env or {},
            "cwd": cwd or os.getcwd(),
        }

    def load_from_config(self, config_data: Dict[str, Any]) -> None:
        """Loads server configurations from sympose master config.yaml."""
        mcp_cfg = config_data.get("mcp_servers", {})
        if isinstance(mcp_cfg, list):
            for s in mcp_cfg:
                if isinstance(s, dict) and "name" in s and "command" in s:
                    self.register_server(
                        name=s["name"],
                        command=s["command"],
                        args=s.get("args", []),
                        env=s.get("env", {}),
                        cwd=s.get("cwd"),
                    )
        elif isinstance(mcp_cfg, dict):
            for name, s in mcp_cfg.items():
                if isinstance(s, dict) and "command" in s:
                    self.register_server(
                        name=name,
                        command=s["command"],
                        args=s.get("args", []),
                        env=s.get("env", {}),
                        cwd=s.get("cwd"),
                    )

    def get_client(self, name: str) -> Optional[MCPClient]:
        """Creates or retrieves an active MCPClient instance for the requested server."""
        name_key = name.lower()
        if name_key in self.active_clients:
            client = self.active_clients[name_key]
            if client.is_connected:
                return client

        if name_key not in self.servers:
            return None

        cfg = self.servers[name_key]
        client = MCPClient(
            name=cfg["name"],
            command=cfg["command"],
            args=cfg["args"],
            env=cfg["env"],
            cwd=cfg["cwd"],
        )
        self.active_clients[name_key] = client
        return client

    def shutdown_all(self) -> None:
        """Stops all running MCP clients."""
        for client in list(self.active_clients.values()):
            client.stop()
        self.active_clients.clear()


# Master singleton registry
mcp_registry = MCPRegistry()
