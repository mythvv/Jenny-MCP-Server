# Jenny MCP Server

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](./LICENSE)
[![Python ≥3.11](https://img.shields.io/badge/Python-%E2%89%A53.11-blue.svg)](https://www.python.org/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io/)

> A plugin-based MCP tool server with dynamic toolkit switching, automatic discovery, and resource lease management.

Jenny MCP Server is a tool server built on [FastMCP](https://github.com/modelcontextprotocol/python-sdk) that provides dynamically switchable toolkits for AI assistants. It wraps coding agents like Droid and OpenCode, along with data analysis, web scraping, and Chinese Metaphysics (Bazi / Qi Men Dun Jia / Zi Wei Dou Shu / Western Astrology), as standard MCP tools — any MCP-compatible client can call them directly.

## Table of Contents

- [Features](#%E2%9C%A8-features)
- [Architecture](#architecture)
- [Directory Structure](#directory-structure)
- [Quick Start](#quick-start)
- [Password Authentication](#%E2%9C%85-password-authentication)
- [Client Configuration](#-client-configuration)
- [Usage](#usage)
- [Plugin Toolkit Reference](#%E2%9C%A8-plugin-toolkit-reference)
- [Creating a Plugin](#creating-a-plugin)
- [Design Principles](#design-principles)
- [License](#license)

## ✨ Features

- 🔄 **Dynamic Toolkit Switching** — Switch toolkits at runtime; tool lists update automatically
- 🧩 **Plugin Auto-Discovery** — Drop a `.py` file or package into `toolkits/plugins/`, restart to activate
- 🤖 **Multiple Coding Agents** — Supports [Factory Droid](https://docs.factory.ai/) (file pipe) and [OpenCode](https://opencode.ai/) (HTTP API)
- 📊 **Data Analysis** — CSV query/stats/visualization, JSON path queries
- 🌐 **Web Scraping** — JS-rendered fetching, batch concurrency, enhanced search, browser login
- 🔮 **Chinese Metaphysics** — Bazi (Four Pillars), Qi Men Dun Jia, Zi Wei Dou Shu, Western Astrology
- ⏱ **Resource Lease** — Built-in TTL-based resource reclamation (sessions, browsers, processes)
- 📜 **Zero Framework Knowledge** — `server.py` knows nothing about plugins; add new tools without touching the core

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       MCP Client (any)                              │
│            Claude / Jenny / Cursor / ...                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ MCP (Streamable HTTP)
                                │ :31415/mcp
┌───────────────────────────────▼─────────────────────────────────────┐
│                       MCP Server (FastMCP)                          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │              Common Tools (always visible)                      │ │
│ │   toolkit_list / toolkit_switch / toolkit_current               │ │
│ │              exec_tool (universal entry)                        │ │
│ └──────────────────────────┬──────────────────────────────────────┘ │
│                            │ Dynamic switching                      │
│ ┌──────────┬──────────┬────┴───────────┬──────────┬───────────────┐ │
│ │  Droid   │ OpenCode │ DataAnalysis   │ Web      │ Chinese Meta. │ │
│ │  (pipe)  │(HTTP API)│ (CSV/JSON)     │ Enhanced │ Bazi|QiMen    │ │
│ │          │          │                │(JS render│ |ZiWei|Astro   │ │
│ └────┬─────┴────┬─────┴──────┬────────┴─────┬────┴───────┬───────┘ │
└──────┼──────────┼────────────┼──────────────┼────────────┼─────────┘
       │          │            │              │            │
  ┌────▼────┐┌────▼────┐┌─────▼────┐┌───────▼──────┐┌────▼──────────┐
  │  Droid  ││OpenCode ││ Pandas   ││  Playwright   ││lunar_python   │
  │   CLI   ││  Serve  ││ + Mpl    ││ + AIOHTTP     ││+ephem+kerykeion│
  └─────────┘└─────────┘└──────────┘└───────────────┘└───────────────┘
```

## Directory Structure

```
jenny-mcp-server/
├── server.py              # Entry point — FastMCP server + auth middleware
├── start.sh / stop.sh / restart.sh   # Service management scripts
├── requirements.txt       # Python dependencies
├── toolkits/
│   ├── __init__.py        # Exports BaseToolkit, ToolkitManager
│   ├── base.py            # BaseToolkit with Lease mechanism
│   ├── manager.py         # Plugin discovery & dispatch
│   └── plugins/           # All toolkits live here
│       ├── droid.py
│       ├── opencode.py
│       ├── data_analysis.py
│       ├── web_enhanced.py
│       ├── astrology.py
│       ├── bazi2/
│       ├── qimen2/
│       └── ziwei2/
└── logs/                  # Auto-created runtime logs
```

## Quick Start

```bash
# Clone
git clone https://github.com/mythvv/jenny-mcp-server.git
cd jenny-mcp-server

# Start (auto-creates venv and installs dependencies)
bash start.sh

# Stop / Restart
bash stop.sh
bash restart.sh

# Default: 0.0.0.0:31415/mcp
# Override with environment variables:
MCP_HOST=127.0.0.1 MCP_PORT=8080 bash start.sh
```

### Prerequisites for Web Scraping

The `web_enhanced` plugin uses Playwright for JS-rendered page fetching. After the initial `pip install`, install browser binaries:

```bash
.venv/bin/playwright install chromium
```

> Without this step, the `web_enhanced` toolkit will fail with "playwright not installed". Other toolkits are unaffected.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Server listen address |
| `MCP_PORT` | `31415` | Server listen port |
| `MCP_PASSWORD` | *(empty)* | Bearer token password; no auth when empty |
| `ALLOWED_HOSTS` | `127.0.0.1:*,localhost:*` | Comma-separated allowed host patterns |
| `DROID_BIN` | `/root/.local/bin/droid` | Droid binary path |
| `OPENCODE_BIN` | `/root/.opencode/bin/opencode` | OpenCode binary path |

### Logging

Logs are written to `logs/server.log` with automatic rotation:

- **10MB** per file, **3** backups retained
- Plugin lifecycle events (startup/shutdown/lease) are all logged

```bash
tail -f logs/server.log
grep "\[lease\]" logs/server.log
```

## 🔐 Password Authentication

Jenny MCP Server supports optional Bearer Token authentication to protect your MCP endpoint.

### How It Works

- Set the `MCP_PASSWORD` environment variable before starting the server
- When set, all requests must include `Authorization: Bearer <your-password>` header
- When **not set** (default), the server runs with **no authentication** — fully backward compatible

### Server Side

```bash
# Start with password protection
export MCP_PASSWORD="your-secret-password"
bash start.sh

# Or inline
MCP_PASSWORD="your-secret-password" bash start.sh

# Start without authentication (default behavior)
bash start.sh
```

### Client Side (Jenny App)

When adding an MCP server in **Settings → MCP Servers**:

1. Fill in the server URL (e.g. `http://192.168.1.100:31415/mcp`)
2. Enter the same password in the **Password** field
3. The app automatically sends `Authorization: Bearer <password>` with every request

> **Note:** If the server has no password configured, leave the password field empty.

### Security Notes

- Password is compared using `hmac.compare_digest` (constant-time) to prevent timing attacks
- Transported in plain text over HTTP — **use only on trusted networks** or pair with HTTPS/TLS
- For production exposure, consider a reverse proxy (nginx/caddy) with TLS termination

## 🔗 Client Configuration

Below are example configurations for common MCP clients. All connect to `http://localhost:31415/mcp` (adjust host/port as needed).

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jenny": {
      "url": "http://localhost:31415/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-password"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "jenny": {
      "url": "http://localhost:31415/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-password"
      }
    }
  }
}
```

### Jenny App

Go to **Settings → MCP Servers → Add**:

- **URL:** `http://<server-ip>:31415/mcp`
- **Password:** `your-secret-password` (leave empty if no auth)

> If the server does not use password auth, omit the `headers` / `Authorization` field entirely.

## Usage

After connecting an MCP client:

1. `toolkit_list` — List all available toolkits
2. `toolkit_switch` — Switch to a target toolkit
3. After switching, the toolkit's tools are auto-registered, or use `exec_tool` as a universal entry point

```
toolkit_list()                    → See available toolkits
toolkit_switch("droid")           → Switch to Droid toolkit
start_session()                   → Start a Droid session
send_message(session_id, "...")   → Send a message
toolkit_switch("data_analysis")   → Switch to data analysis
csv_query(file_path="/tmp/data.csv", query="...")
toolkit_switch("bazi2")           → Switch to Bazi
toolkit_switch("qimen2")          → Switch to Qi Men Dun Jia
toolkit_switch("ziwei2")          → Switch to Zi Wei Dou Shu
toolkit_switch("astrology")       → Switch to Western Astrology
```

## 📦 Plugin Toolkit Reference

### 🤖 Droid — AI Coding Agent (File Pipe)

Wraps [Factory Droid](https://docs.factory.ai/) CLI as MCP tools. Sessions communicate via JSONL file pipes.

| Tool | Description |
|------|-------------|
| `start_session` | Start a Droid session (supports model, auto_level, cwd, session resume) |
| `send_message` | Send a message to a session (async, poll for reply) |
| `poll_output` | Get latest output from a session (supports incremental reading) |
| `check_status` | Check session status; list all sessions if no ID given |
| `stop_session` | Stop the specified session |
| `exec_and_wait` | One-shot: create → send → wait → return results |
| `interrupt_session` | Interrupt running task (SIGINT), preserving session context |
| `get_history` | View session conversation history |

**Droid Configuration** — Create `toolkits/plugins/droid_config.json` (auto-detected on startup):

```json
{
  "model": "custom:YOUR_MODEL_HERE",
  "auto_level": "high",
  "reasoning_effort": "none",
  "interaction_mode": "auto",
  "poll_interval_seconds": 30,
  "max_wait_minutes": 15
}
```

> A template is available at `toolkits/plugins/droid_config.example.json`. This file is gitignored since it may contain model IDs.

### 🤖 OpenCode — AI Coding Agent (HTTP API)

Wraps [OpenCode](https://opencode.ai/) as MCP tools via its HTTP API.

| Tool | Description |
|------|-------------|
| `start_session` | Create an OpenCode session (auto-starts serve process) |
| `send_message` | Send a message to a session (async, auto-polls for result) |
| `poll_output` | Get session message list (supports incremental reading) |
| `check_status` | Check session or server status |
| `stop_session` | Delete an OpenCode session |
| `exec_and_wait` | One-shot: create → send → wait → return results |

### 📊 Data Analysis — CSV & JSON

Query, analyze, and visualize tabular data using Pandas + Matplotlib.

| Tool | Description |
|------|-------------|
| `csv_info` | CSV file overview (rows, columns, types, missing values) |
| `csv_analyze` | Statistical analysis on columns (mean, median, quantiles, distribution) |
| `csv_query` | SQL-style filtering/sorting on CSV data |
| `csv_chart` | Generate charts (line/bar/scatter/pie/histogram) as PNG |
| `json_query` | Parse JSON files with path-based queries |

### 🌐 Web Enhanced — Scraping & Search

Web scraping with JS rendering (Playwright), batch fetching, and enhanced search.

| Tool | Description |
|------|-------------|
| `web_fetch_js` | Fetch page with Playwright JS rendering (CSS selectors, wait, cookies) |
| `web_batch_fetch` | Batch concurrent fetch of multiple URLs |
| `web_search_enhanced` | Enhanced search with time range, site filter, snippet extraction |
| `web_login` | Browser auto-login and cookie saving |

### 🔮 Bazi2 — 八字排盘 (Four Pillars of Destiny)

Chinese birth chart analysis with Five Elements, Da Yun, and Liu Nian.

| Tool | Description |
|------|-------------|
| `bazi2_chart` | 八字排盘（四柱/藏干/十神/纳音/日主/命宫） |
| `bazi2_wuxing` | 五行分析（分布/旺衰/缺补） |
| `bazi2_dayun` | 大运排列（起运年龄/大运/流年） |
| `bazi2_liunian` | 流年分析（当年干支与日主关系） |
| `bazi2_liuyue` | 流月分析（当年各月干支与日主关系） |

### 🔮 Qimen2 — 奇门遁甲 (Mystical Door Escaping Technique)

Qi Men Dun Jia divination with multiple methods.

| Tool | Description |
|------|-------------|
| `qimen2_pan` | 时家奇门排盘（拆补/置闰）— Nine Palaces with full info |
| `qimen2_minute` | 刻家奇门排盘（minute precision） |
| `qimen2_gpan` | 金函玉镜日家奇门（daily method） |
| `qimen2_overall` | 综合运势分析 |

### 🔮 Ziwei2 — 紫微斗数 (Purple Star Astrology)

Zi Wei Dou Shu birth chart with palaces, Da Xian, and Liu Nian.

| Tool | Description |
|------|-------------|
| `ziwei2_chart` | 紫微排盘（命宫身宫/十四主星/四化/亮度/五行局） |
| `ziwei2_palace` | 宫位分析（星曜组合与三方四正） |
| `ziwei2_daxian` | 大限排列（各步大限宫位和星曜） |
| `ziwei2_liunian` | 流年分析（当年命宫/四化/大限） |
| `ziwei2_liuyue` | 流月分析（当年各月命宫/四化） |

### 🔮 Astrology — Western Astrology

Western astrology with natal charts, horoscopes, and synastry.

| Tool | Description |
|------|-------------|
| `natal_chart` | Birth chart: Sun/Moon/Rising signs, planets, houses, aspects |
| `horoscope` | Daily horoscope based on current transits |
| `synastry` | Compatibility analysis between two birth charts |
| `retrogrades` | Planetary retrograde status for a given date |
| `moon_phase` | Moon phase info (phase name, Moon sign, illumination) |

## Creating a Plugin

Drop a file or directory into `toolkits/plugins/` and restart. No framework changes needed.

### Single-File Plugin

`toolkits/plugins/my_tool.py`:

```python
from toolkits.base import BaseToolkit

class MyTool(BaseToolkit):
    name = "my_tool"
    description = "My toolkit"

    def __init__(self, ctx=None):
        super().__init__()

    def get_config_schema(self):
        return {}

    def get_tools(self):
        return [
            (self.hello, "hello",
             "Returns a greeting",
             [("name", "str", "World", "Name")]),
        ]

    async def hello(self, name="World"):
        return {"message": f"Hello, {name}!"}
```

### Package Plugin

For larger plugins with sub-modules:

```
plugins/my_tool/
├── __init__.py    # Must export a BaseToolkit subclass
├── core.py
└── tables.py
```

### Key Interfaces

| Method | Required | Description |
|--------|----------|-------------|
| `name` / `description` | Yes | Class attributes |
| `get_config_schema()` | Yes | Return config description dict |
| `get_tools()` | Yes | Return tool list |
| `startup()` | No | Startup hook |
| `shutdown()` | No | Shutdown hook (default: reclaim all Lease resources) |

#### Constructor `__init__(ctx)`

Framework passes a `ctx` dict with `base_dir` (project root). **Must call `super().__init__()`** to initialize Lease mechanism.

```python
def __init__(self, ctx=None):
    super().__init__()
    ctx = ctx or {}
    base = ctx.get("base_dir", "/tmp")
    self.data_dir = Path(base) / "my_tool_data"
```

#### `get_tools()` Format

Each entry is a 4-tuple: `(method, tool_name, description, param_list)`

```python
def get_tools(self):
    return [
        (self.my_func, "my_func",
         "Tool description",
         [("param1", "str", None, "Required param"),
          ("param2", "int", 10, "Optional param"),
          ("param3", "Optional[str]", None, "Optional param")]),
    ]
```

Supported type strings: `str`, `int`, `float`, `bool`, `Optional[str]`, `Optional[int]`, `Optional[float]`

### Duplicate Tool Name Resolution

When two or more toolkits expose a tool with the same name (e.g. both `droid` and `opencode` have `start_session`), the server automatically prefixes the MCP-registered name with the toolkit name:

| Toolkit | Original Name | Registered MCP Name |
|---------|--------------|-------------------|
| droid | `start_session` | `droid__start_session` |
| opencode | `start_session` | `opencode__start_session` |

Non-duplicated names are registered as-is. This is handled by `_registered_name()` and `_DUPES` — computed once at startup via `_detect_duplicate_names()`.

> **Plugin authors**: you do not need to do anything special. Just pick a descriptive name for your tools; the server handles conflicts automatically.


### Resource Lease Mechanism

Built-in TTL-based resource reclamation for sessions, browsers, processes, etc.

```
Create  → _lease(key, ttl, cleanup_fn)   Register, start countdown
Active  → _renew(key)                    Reset countdown
Release → _release(key)                  Cancel countdown
Expired → cleanup_fn() auto-executes     Reclaim resource
Stop    → shutdown()                     Reclaim all active resources
```

**Usage:**

```python
async def start_session(self, ...):
    self._lease(session_id, ttl=1800, lambda: asyncio.ensure_future(self.stop_session(session_id)))

async def send_message(self, session_id, message):
    self._renew(session_id)

async def stop_session(self, session_id):
    self._release(session_id)
```

**Existing Lease usage:**

| Plugin | key | ttl | Cleanup |
|--------|-----|-----|---------|
| droid | session_id | 1800s | Kill idle session process |
| opencode | "serve" | 1800s | Stop serve process when no sessions |
| web_enhanced | "browser" | 600s | Close idle Playwright browser |

## Design Principles

- **server.py knows zero plugins** — No imports, no config reads, no directory creation for plugins
- **manager.py is pure dispatch** — Only passes `base_dir`, never parses plugin configs
- **Plugins are fully self-contained** — Each manages its own config, directories, and resource cleanup
- **Resources reclaimed on demand** — Lease mechanism: no polling, no traversal, zero overhead when idle
- **New plugin = new file** — No framework changes, no registries, restart to activate

## License

[AGPL-3.0](./LICENSE)
