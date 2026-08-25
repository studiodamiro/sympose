# 🔌 Model Context Protocol (MCP) Directory

This directory contains master server definitions and custom tools for Sympose's **Ephemeral Sub-Agent Workers**.

---

## 🏛️ How MCP Works in Sympose

Instead of injecting dozens of heavy tool schemas into the primary conversational agents (saving 4,000+ tokens per turn), Sympose agents dynamically spawn child workers when needed:

```text
User: "Grace, can you check the latest release notes on github.com/fastapi/fastapi?"
Grace -> [SPAWN_WORKER: fetch | Scrape https://github.com/tiangolo/fastapi/releases and summarize v0.115.0]
Worker -> Connects to fetch MCP over stdio -> Executes fetch tool -> Returns crisp summary
Grace -> "FastAPI v0.115.0 was released with support for..."
```

---

## ⚙️ Configured Servers (`mcp/servers.json`)

| Server | Purpose | Authentication |
| :--- | :--- | :--- |
| **`fetch`** | Web page fetching & HTML/markdown scraping | None ($0 / zero-auth) |
| **`filesystem`** | Local workspace file reads and searches | Local directory |
| **`github`** | Pull requests, issue tracking, remote code inspection | `GITHUB_TOKEN` in `.env` |
| **`slack`** | Channel message search, thread inspections | `SLACK_BOT_TOKEN` in `.env` |
| **`brave_search`** | Live internet search | `BRAVE_API_KEY` in `.env` |

---

## 🛠️ Adding a New MCP Server

Add your server definition to `mcp/servers.json`:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "garden.db"]
    }
  }
}
```
