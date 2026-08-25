"""
Model Context Protocol (MCP) Server Registry & Manager.
Auto-discovers server configs from mcp/ directory and master config.yaml.
"""

import os
import json
from typing import Dict, List, Any, Optional
from sympose.mcp_client import MCPClient


class MCPRegistry:
    """Manages available MCP server configurations and active client instances."""

    def __init__(self, mcp_dir: str = "mcp"):
        self.mcp_dir = mcp_dir
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.active_clients: Dict[str, MCPClient] = {}
        self.auto_discover()

    def register_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> None:
        self.servers[name.lower()] = {
            "name": name.lower(),
            "command": command,
            "args": args or [],
            "env": env or {},
            "cwd": cwd or os.getcwd(),
        }

    def auto_discover(self) -> None:
        """Discovers MCP servers from mcp/servers.json or mcp/*.json files."""
        candidates = [
            os.path.join(self.mcp_dir, "servers.json"),
            os.path.join(self.mcp_dir, "mcp_config.json"),
            os.path.join(self.mcp_dir, "servers.json.example"),
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    srvs = data.get("mcpServers") or data.get("servers") or data
                    if isinstance(srvs, dict):
                        for name, s in srvs.items():
                            if isinstance(s, dict) and "command" in s:
                                self.register_server(
                                    name=name,
                                    command=s["command"],
                                    args=s.get("args", []),
                                    env=s.get("env", {}),
                                    cwd=s.get("cwd"),
                                )
                        break
                except Exception as e:
                    print(f"⚠️ Error parsing MCP config [{c}]: {e}")

    def load_from_config(self, config_data: Dict[str, Any]) -> None:
        """Loads fallback server configurations from sympose config.yaml."""
        mcp_cfg = config_data.get("mcp_servers", {})
        if isinstance(mcp_cfg, dict):
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
        for client in list(self.active_clients.values()):
            client.stop()
        self.active_clients.clear()


# Master singleton registry
mcp_registry = MCPRegistry()
