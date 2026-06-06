# Contributing Guide

Thank you for your interest in Jenny MCP Server! We welcome Issues and Pull Requests.

## Quick Start

```bash
# 1. Fork and clone
git clone https://github.com/your-username/jenny-mcp-server.git
cd jenny-mcp-server

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser (optional, for web-enhanced toolkit)
.venv/bin/playwright install chromium

# 5. Start the server
bash start.sh
```

## Development Flow

### Branch Management

- `main` — stable release branch
- `dev` — development integration branch
- Feature branches: `feat/your-feature`
- Fix branches: `fix/your-fix`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add xxx toolkit
fix: fix session timeout not working
docs: update API documentation
refactor: refactor tool registration mechanism
chore: update dependency versions
```

### Code Style

- Lint: `ruff check .`
- Format: `ruff format`
- Type annotations required on public APIs
- Docstrings required on all tool functions

## Adding a New Toolkit

### Plugin Auto-Discovery

Toolkits placed in `toolkits/plugins/` are auto-discovered at startup — no registration code needed.

### Step-by-step

1. Create a new `.py` file or package under `toolkits/plugins/`
2. Inherit from `BaseToolkit` and implement `get_tools()`:

```python
from toolkits.base import BaseToolkit

class MyToolkit(BaseToolkit):
    name = "my_toolkit"

    def get_tools(self):
        return [
            (self.my_func, "my_func",
             "Description of what this tool does",
             [("param1", "str", None, "Required parameter"),
              ("param2", "int", 10, "Optional parameter with default"),
              ("param3", "Optional[str]", None, "Truly optional parameter")]),
        ]

    async def my_func(self, param1: str, param2: int = 10, param3: str = None):
        """Tool implementation."""
        return {"result": param1}
```

3. Restart the server — the plugin is loaded and its tools are registered automatically.

### How Registration Works Internally

You do **not** need to modify `server.py` or `manager.py`. The startup sequence:

1. `ToolkitManager` discovers all `BaseToolkit` subclasses in `toolkits/plugins/`
2. Each toolkit's `get_tools()` builds `_TOOL_REGISTRY` (a dict of toolkit name → tool map)
3. `_register_all_tools_static()` registers all tools as MCP tools with tags
4. Tools with **duplicate names across toolkits** are auto-prefixed (e.g. `droid__start_session`)
5. All toolkit tools start **disabled**; clients call `toolkit_switch` to enable them per-session

Supported type strings: `str`, `int`, `float`, `bool`, `Optional[str]`, `Optional[int]`, `Optional[float]`

### Resource Lease Mechanism

For toolkits that manage resources (sessions, browsers, processes), use the built-in TTL-based lease:

```python
async def start_session(self, ...):
    self._lease(session_id, ttl=1800,
                lambda: asyncio.ensure_future(self.stop_session(session_id)))

async def send_message(self, session_id, message):
    self._renew(session_id)  # reset TTL countdown

async def stop_session(self, session_id):
    self._release(session_id)
```

## Scripts

| Script | Purpose |
|--------|---------|
| `start.sh` | Start server (reads `.env` for `MCP_PASSWORD`, `MCP_HOST`, `MCP_PORT`) |
| `stop.sh` | Graceful stop with fallback to force-kill |
| `restart.sh` | Stop then start |

## Pull Request Process

1. Ensure code style: `ruff check .`
2. Update relevant documentation (README, CHANGELOG)
3. Submit a PR describing changes and motivation
4. Wait for review

## Issue Reports

Please include:

- **Environment**: Python version, OS, relevant tool versions
- **Reproduction steps**: Minimal reproducible steps
- **Expected vs actual behavior**
- **Logs**: Relevant error output (remove sensitive information first)

## License

By submitting code, you agree to license your contributions under [AGPL-3.0](./LICENSE).
