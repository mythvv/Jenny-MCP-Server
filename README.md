# Jenny MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python ≥3.11](https://img.shields.io/badge/Python-%E2%89%A53.11-blue.svg)](https://www.python.org/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io/)

> A lightweight tool server that unifies AI coding agents, data analysis, and web scraping via the MCP (Model Context Protocol) protocol.

Jenny MCP Server is a tool server built on [FastMCP](https://github.com/modelcontextprotocol/python-sdk) that provides dynamically switchable toolkits for AI assistants. It wraps coding agents like Droid and OpenCode, along with data analysis and web scraping capabilities, as standard MCP tools — any MCP-compatible client can call them directly.

## ✨ Features

- 🔄 **Dynamic Toolkit Switching** — Switch toolkits at runtime; tool lists update automatically
- 🤖 **Multiple Coding Agents** — Supports [Factory Droid](https://docs.factory.ai/) (file pipe) and [OpenCode](https://opencode.ai/) (HTTP API)
- 📊 **Data Analysis** — CSV query/stats/visualization, JSON path queries
- 🌐 **Web Scraping** — JS-rendered fetching, batch concurrency, enhanced search, browser login
- ⏱ **Session Management** — Auto GC, idle timeout reclamation, orphan session cleanup
- 📜 **Shell Scripts** — Bundled start/send/poll/status scripts for direct CLI interaction

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
│  └─────────────────────┬───────────────────────────┘  │
│                        │ Dynamic switching             │
│  ┌─────────┬───────────┼───────────┬──────────────┐   │
│  │  Droid  │ OpenCode  │DataAnalysis│ WebEnhanced │   │
│  │ (pipe)  │(HTTP API) │(CSV/JSON) │(JS render)  │   │
│  └────┬────┴─────┬─────┴─────┬─────┴──────┬──────┘   │
└───────┼──────────┼───────────┼────────────┼───────────┘
        │          │           │            │
   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌────▼─────┐
   │  Droid │ │OpenCode│ │Pandas  │ │Playwright│
   │  CLI   │ │ Serve  │ │+Mpl    │ │ +AIOHTTP │
   └────────┘ └────────┘ └────────┘ └──────────┘
```

### Session Model

```
                    Droid (File Pipe Mode)
 ┌────────┐  input.jsonl   ┌──────────┐
 │ Client │ ──────────────►│  droid   │
 │        │  (JSON-RPC)    │  exec    │
 │        │◄────────────── │  (tail)  │
 └────────┘  output.jsonl  └──────────┘

                    OpenCode (HTTP API Mode)
 ┌────────┐   POST /session/{id}/message   ┌──────────┐
 │ Server │ ──────────────────────────────► │ opencode │
 │        │ ◄────────────────────────────── │  serve   │
 └────────┘   JSON response (sync wait)     └──────────┘
```

## Directory Structure

```
jenny-mcp-server/
├── config/
│   └── defaults.example.json   # Configuration template
├── mcp-server/
│   ├── server.py               # MCP server entry + tool routing
│   ├── requirements.txt        # Python dependencies
│   └── toolkits/
│       ├── __init__.py         # Toolkit exports
│       ├── base.py             # Abstract base class BaseToolkit
│       ├── manager.py          # Toolkit manager ToolkitManager
│       ├── droid.py            # Droid toolkit
│       ├── opencode.py         # OpenCode toolkit
│       ├── data_analysis.py    # Data analysis toolkit
│       └── web_enhanced.py     # Web enhanced toolkit
├── scripts/
│   ├── start.sh                # Start a Droid session
│   ├── send.sh                 # Send message to session
│   ├── poll.sh                 # Poll session output
│   └── status.sh               # View session status
├── sessions/                   # Session data (generated at runtime)
├── workspace/                  # Agent workspace (generated at runtime)
└── README.md
```

## Installation

### Prerequisites

- Python 3.11+
- [Factory Droid CLI](https://docs.factory.ai/) (only for Droid toolkit)
- [OpenCode](https://opencode.ai/) (only for OpenCode toolkit)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/jenny-mcp-server.git
cd jenny-mcp-server

# 2. Create virtual environment and install dependencies
cd mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional dependencies (install as needed)
pip install httpx                # OpenCode toolkit
pip install pandas matplotlib    # Data analysis toolkit
pip install playwright aiohttp   # Web enhanced toolkit
playwright install chromium      # Install browser

# 3. Create configuration file
cp ../config/defaults.example.json ../config/defaults.json
# Edit defaults.json with actual settings
```

## Usage

### Starting the Server

```bash
cd mcp-server
source .venv/bin/activate

# Default: 0.0.0.0:31415
python server.py

# Custom address
python server.py --host 127.0.0.1 --port 8080
```

The server endpoint is `http://<host>:<port>/mcp` (Streamable HTTP transport).

### Client Configuration

Add the following to your MCP client configuration:

```json
{
  "mcpServers": {
    "jenny-tools": {
      "url": "http://127.0.0.1:31415/mcp"
    }
  }
}
```

### Shell Scripts (Droid Direct Interaction)

```bash
# Start a new session, returns session-id
SESSION=$(./scripts/start.sh)
echo "Session: $SESSION"

# Send a message
./scripts/send.sh "$SESSION" "Create a hello world Python script"

# Poll output
./scripts/poll.sh "$SESSION" 0    # Read from line 0

# View all session statuses
./scripts/status.sh

# View a specific session
./scripts/status.sh "$SESSION"
```

## API Reference

### Common Tools

These three tools are available regardless of which toolkit is active.

#### `toolkit_list`

List all available toolkits and their tools.

**Parameters:** None

**Response example:**

```json
{
  "toolkits": {
    "droid": { "description": "Factory Droid - File pipe mode", "tools": [...] },
    "opencode": { "description": "OpenCode - HTTP API multi-turn session mode", "tools": [...] },
    "data_analysis": { "description": "Data Analysis - CSV query/stats/visualization", "tools": [...] },
    "web_enhanced": { "description": "Web Enhanced - JS rendered scraping", "tools": [...] }
  }
}
```

#### `toolkit_switch`

Switch the active toolkit; tool list updates automatically.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ | Toolkit name: `droid` / `opencode` / `data_analysis` / `web_enhanced` |
| `config` | string | ❌ | JSON configuration parameters |

**Config examples:**

```jsonc
// Droid
{ "model": "custom:YOUR_MODEL", "auto_level": "high", "cwd": "/path/to/project" }

// OpenCode
{ "model": "opencode/big-pickle", "workdir": "/path/to/project" }
```

#### `toolkit_current`

Display the current toolkit name and available tools.

---

### 🤖 Droid Toolkit

Interacts with [Factory Droid](https://docs.factory.ai/) via file pipe (`tail -f input.jsonl | droid exec`). Each session gets an independent directory, supporting multi-turn conversations.

#### `start_session`

Create a new Droid session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config` | object | ❌ | Override default settings (model, auto_level, cwd, etc.) |

**Returns:** `{ "session_id": "uuid", "status": "started", "pid": 12345, "session_dir": "/path" }`

#### `send_message`

Send a message to a session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |
| `message` | string | ✅ | Message content |

#### `poll_output`

Poll session output with incremental reading support.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |
| `last_line` | int | ❌ | Line number last read; only returns content after this line |

**Returns:** `{ "lines": [...], "total_lines": 42 }`

#### `check_status`

Check session status.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |

#### `stop_session`

Stop and clean up a session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |

#### `exec_and_wait`

All-in-one execution: create session → send message → wait for completion → return output.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | ✅ | Message to execute |
| `timeout` | int | ❌ | Timeout in seconds, default 900 (15 min) |
| `config` | object | ❌ | Session configuration |

---

### 🔮 OpenCode Toolkit

Interacts with [OpenCode](https://opencode.ai/) via HTTP API. Automatically manages the lifecycle of the `opencode serve` process.

#### `start_session`

Start opencode serve and create a session. Auto-detects existing serve processes and starts one if needed.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config` | object | ❌ | `model` (e.g. `"opencode/big-pickle"`), `workdir` |

#### `send_message`

Send a message to an OpenCode session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |
| `message` | string | ✅ | Message content |

#### `poll_output`

Poll OpenCode session output.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |
| `last_line` | int | ❌ | Line number last read |

#### `check_status`

Check OpenCode session status.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |

#### `stop_session`

Stop an OpenCode session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | ✅ | Session ID |

#### `exec_and_wait`

All-in-one OpenCode execution.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | ✅ | Message to execute |
| `timeout` | int | ❌ | Timeout in seconds |
| `config` | object | ❌ | Session configuration |

#### `cleanup`

Clean up all stopped sessions and the serve process.

---

### 📊 Data Analysis Toolkit

CSV and JSON data analysis tools powered by Pandas and Matplotlib.

#### `csv_info`

Get basic information about a CSV file (columns, types, shape, preview).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | CSV file path |
| `preview_rows` | int | ❌ | Number of preview rows, default 5 |

#### `csv_analyze`

Statistical analysis of CSV data (describe, group by, etc.).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | CSV file path |
| `operation` | string | ❌ | Operation: `describe` / `groupby`, default `describe` |
| `group_by` | string | ❌ | Group by column (required when operation is `groupby`) |
| `agg_column` | string | ❌ | Column to aggregate (required when operation is `groupby`) |
| `agg_func` | string | ❌ | Aggregation: `mean` / `sum` / `count` / `min` / `max`, default `mean` |

#### `csv_query`

Query CSV data using SQL-style expressions (based on Pandas DataFrame.query).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | CSV file path |
| `query` | string | ✅ | Query expression, e.g. `"age > 30 & city == 'Beijing'"` |
| `columns` | string | ❌ | Columns to select, comma-separated, e.g. `"name,age,city"` |

#### `csv_chart`

CSV data visualization (generates chart and saves as PNG).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | CSV file path |
| `chart_type` | string | ✅ | Chart type: `line` / `bar` / `scatter` / `pie` |
| `x_column` | string | ✅ | X-axis column name |
| `y_column` | string | ✅ | Y-axis column name (value column for pie charts) |
| `title` | string | ❌ | Chart title |

**Returns:** `{ "chart_path": "/tmp/data_analysis_charts/chart_xxx.png", "data_points": 100 }`

#### `json_query`

JSON file path query.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | JSON file path |
| `path` | string | ❌ | Query path, e.g. `users[0].name`, default `.` (root) |
| `pretty` | bool | ❌ | Pretty-print output, default `true` |

---

### 🌐 Web Enhanced Toolkit

Advanced web scraping tools powered by Playwright + AIOHTTP.

#### `web_fetch_js`

Fetch page content after JavaScript rendering via Playwright.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | ✅ | Target URL |
| `selector` | string | ❌ | CSS selector, extract only matching elements |
| `wait_for` | string | ❌ | Wait for selector to appear before fetching |
| `timeout` | int | ❌ | Timeout in seconds, default 30 |
| `use_cookies` | string | ❌ | Cookie file path (generated by web_login) |

#### `web_batch_fetch`

Batch concurrent fetching of multiple URLs.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | string | ✅ | URL list in JSON array format |
| `max_concurrent` | int | ❌ | Max concurrency, default 5 |
| `timeout` | int | ❌ | Timeout per request in seconds, default 30 |

#### `web_search_enhanced`

Enhanced search (supports time/site filtering, content extraction).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ | Search keywords |
| `max_results` | int | ❌ | Max results, default 10 |
| `time_range` | string | ❌ | Time range: `day` / `week` / `month` / `year` |
| `site` | string | ❌ | Restrict to site, e.g. `github.com` |
| `fetch_content` | bool | ❌ | Whether to fetch result page content, default `false` |

#### `web_login`

Browser login and save cookies.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | ✅ | Login page URL |
| `username_selector` | string | ✅ | Username input CSS selector |
| `password_selector` | string | ✅ | Password input CSS selector |
| `username` | string | ✅ | Username |
| `password` | string | ✅ | Password |
| `submit_selector` | string | ❌ | Submit button selector (press Enter if empty) |
| `cookies_file` | string | ❌ | Cookie save path |
| `wait_after_login` | int | ❌ | Seconds to wait after login, default 3 |
| `verify_selector` | string | ❌ | Selector to verify successful login |

---

## Configuration

Copy the template and modify:

```bash
cp config/defaults.example.json config/defaults.json
```

`config/defaults.json`:

```json
{
  "model": "custom:YOUR_MODEL_HERE",
  "auto_level": "high",
  "reasoning_effort": "none",
  "interaction_mode": "auto",
  "cwd": "/path/to/workspace",
  "poll_interval_seconds": 30,
  "max_wait_minutes": 15
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `model` | Model used by Droid | — |
| `auto_level` | Auto execution level `low` / `medium` / `high` | `high` |
| `reasoning_effort` | Reasoning intensity `none` / `low` / `medium` / `high` | `none` |
| `interaction_mode` | Interaction mode | `auto` |
| `cwd` | Agent working directory | Project workspace directory |
| `poll_interval_seconds` | Polling interval | `30` |
| `max_wait_minutes` | Maximum wait time | `15` |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DROID_BIN` | Path to Droid CLI | `droid` |

## Development

### Adding a New Toolkit

1. Create a new file under `mcp-server/toolkits/`, inheriting from `BaseToolkit`:

```python
from .base import BaseToolkit

class MyToolkit(BaseToolkit):
    name = "my_toolkit"
    description = "My toolkit"

    def get_config_schema(self) -> dict:
        return {"key": "description"}

    def get_tools(self) -> list:
        return [
            (self.my_tool, "my_tool", "Tool description"),
        ]

    async def my_tool(self, param: str) -> dict:
        return {"result": "..."}
```

2. Export it in `toolkits/__init__.py`
3. Register it in `toolkits/manager.py`
4. Add tool routing in `server.py` (using the `@_reg` decorator)

## License & Compliance

### This Project

Jenny MCP Server is released under the **MIT License** (see [LICENSE](./LICENSE)).

### Third-Party Components

This tool server integrates with the following third-party tools via standard interfaces. These tools are **not included** in this project's distribution:

| Component | License | Notes |
|-----------|---------|-------|
| [Factory Droid](https://docs.factory.ai/) | Proprietary (Source Available) | Integrated via `droid exec --input-format stream-jsonrpc` public CLI interface. Droid is a proprietary product of Factory AI, Copyright © 2025-2026 Factory AI. All rights reserved. |
| [OpenCode](https://opencode.ai/) | MIT License | Integrated via `opencode serve` HTTP API. OpenCode is open-sourced under MIT. |
| [FastMCP](https://github.com/modelcontextprotocol/python-sdk) | MIT License | MCP Protocol Python SDK |
| [Playwright](https://playwright.dev/) | Apache 2.0 | Browser automation engine |
| [Pandas](https://pandas.pydata.org/) | BSD 3-Clause | Data analysis library |
| [Matplotlib](https://matplotlib.org/) | PSF License | Chart visualization library |

### Disclaimer

- This project does **not distribute or embed** binaries or source code of Droid, OpenCode, or other third-party tools
- Users must install and comply with each component's terms of use
- This project is not affiliated with or endorsed by Factory AI, OpenCode, or any other third-party team
