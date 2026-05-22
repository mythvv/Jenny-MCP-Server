# Jenny MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python ≥3.11](https://img.shields.io/badge/Python-%E2%89%A53.11-blue.svg)](https://www.python.org/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io/)

> A plugin-based MCP tool server with dynamic toolkit switching, automatic discovery, and resource lease management.

Jenny MCP Server is a tool server built on [FastMCP](https://github.com/modelcontextprotocol/python-sdk) that provides dynamically switchable toolkits for AI assistants. It wraps coding agents like Droid and OpenCode, along with data analysis, web scraping, and Chinese metaphysics (八字/奇门遁甲/紫微斗数/占星), as standard MCP tools — any MCP-compatible client can call them directly.

## ✨ Features

- 🔄 **Dynamic Toolkit Switching** — Switch toolkits at runtime; tool lists update automatically
- 🧩 **Plugin Auto-Discovery** — Drop a `.py` file or package into `toolkits/plugins/`, restart to activate
- 🤖 **Multiple Coding Agents** — Supports [Factory Droid](https://docs.factory.ai/) (file pipe) and [OpenCode](https://opencode.ai/) (HTTP API)
- 📊 **Data Analysis** — CSV query/stats/visualization, JSON path queries
- 🌐 **Web Scraping** — JS-rendered fetching, batch concurrency, enhanced search, browser login
- 🔮 **Chinese Metaphysics** — 八字命理 (Bazi), 奇门遁甲 (Qi Men), 紫微斗数 (Zi Wei), 西方占星 (Astrology)
- ⏱ **Resource Lease** — Built-in TTL-based resource reclamation (sessions, browsers, processes)
- 📜 **Zero Framework Knowledge** — `server.py` knows nothing about plugins; add new tools without touching the core

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  MCP Client (any)                     │
│          Claude / Jenny / Cursor / ...                │
└──────────────────────┬───────────────────────────────┘
                       │ MCP (Streamable HTTP)
                       │ :31415/mcp
┌──────────────────────▼───────────────────────────────┐
│                  MCP Server (FastMCP)                  │
│  ┌─────────────────────────────────────────────────┐  │
│  │           Common Tools (always visible)          │  │
│  │   toolkit_list / toolkit_switch / toolkit_current│  │
│  │              exec_tool (universal entry)         │  │
│  └─────────────────────┬───────────────────────────┘  │
│                        │ Dynamic switching             │
│  ┌─────────┬──────────┼───────────┬────────────┬───────────────────┐  │
│  │  Droid  │ OpenCode │DataAnalysis│WebEnhanced │  Chinese Meta.   │  │
│  │ (pipe)  │(HTTP API)│(CSV/JSON) │(JS render) │八字/奇门/紫微/占星│  │
│  └────┬────┴────┬─────┴─────┬─────┴──────┬─────┴────────┬─────────┘  │
└───────┼─────────┼───────────┼────────────┼──────────────┼────────────┘
        │         │           │            │              │
   ┌────▼───┐┌───▼────┐┌────▼───┐┌────▼─────┐┌──────────▼─────────┐
   │  Droid ││OpenCode││Pandas  ││Playwright││lunar_python+ephem  │
   │  CLI   ││ Serve  ││+Mpl    ││ +AIOHTTP ││+kerykeion+sxtwl   │
   └────────┘└────────┘└────────┘└──────────┘└────────────────────┘
```

## Directory Structure

```
jenny-mcp-server/
├── server.py              # Framework entry point (zero plugin knowledge)
├── requirements.txt       # Python dependencies
├── start.sh / stop.sh / restart.sh  # Process management scripts
│
└── toolkits/
    ├── __init__.py         # Exports BaseToolkit + ToolkitManager
    ├── base.py             # Abstract base (lifecycle hooks + Lease + auto param extraction)
    ├── manager.py          # Plugin discovery + registration + switching
    │
    └── plugins/            # All toolkits (auto-discovered)
        ├── droid.py            # Droid file-pipe mode (coding agent)
        ├── droid_config.json   # Droid private config (gitignored)
        ├── opencode.py         # OpenCode HTTP API mode (coding agent)
        ├── data_analysis.py    # CSV/JSON analysis + visualization
        ├── web_enhanced.py     # JS rendering / batch fetch / search / login
        ├── astrology.py        # Western astrology (Kerykeion)
        ├── bazi2/              # 八字命理 (Bazi / Four Pillars)
        ├── qimen2/             # 奇门遁甲 (Qi Men Dun Jia)
        └── ziwei2/             # 紫微斗数 (Zi Wei Dou Shu)

# Auto-generated at runtime
logs/                      # RotatingFileHandler (10MB per file, 3 backups)
```

## Quick Start

```bash
# Clone
git clone https://github.com/mythvv/jenny-mcp-server.git
cd jenny-mcp-server

# Start (auto-creates venv and installs dependencies)
bash start.sh

# Default: 0.0.0.0:31415/mcp
# Override with environment variables:
MCP_HOST=127.0.0.1 MCP_PORT=8080 bash start.sh

# Stop / Restart
bash stop.sh
bash restart.sh
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Server listen address |
| `MCP_PORT` | `31415` | Server listen port |
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
toolkit_switch("bazi2")           → Switch to 八字命理
toolkit_switch("qimen2")          → Switch to 奇门遁甲
toolkit_switch("ziwei2")          → Switch to 紫微斗数
toolkit_switch("astrology")       → Switch to 西方占星
```

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

[MIT](./LICENSE)
