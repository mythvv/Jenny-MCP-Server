import hmac
import inspect
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

from toolkits import ToolkitManager
from toolkits.base import BaseToolkit

PROJECT_DIR = Path(__file__).resolve().parent

LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_handler = RotatingFileHandler(
    LOG_DIR / "server.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s"))
_handler.setLevel(logging.INFO)

logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("toolkits").setLevel(logging.DEBUG)

log = logging.getLogger("mcp-server")

mcp = FastMCP("tools")

# ── Auth middleware ──────────────────────────────────────────────
MCP_PASSWORD = os.environ.get("MCP_PASSWORD", "")
log.info("auth: password %s", "enabled" if MCP_PASSWORD else "disabled")


class _AuthHeaders:
    """Starlette-style middleware for bearer token auth."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        if not MCP_PASSWORD:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="replace")

        if not auth_header.startswith("Bearer "):
            await _send_json(send, 401, {"error": "Unauthorized", "detail": "Missing or invalid Authorization header"})
            return

        token = auth_header[7:]
        if not hmac.compare_digest(token, MCP_PASSWORD):
            await _send_json(send, 403, {"error": "Forbidden", "detail": "Invalid password"})
            return

        await self.app(scope, receive, send)


async def _send_json(send, status: int, body: dict):
    raw = json.dumps(body).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(raw)).encode()],
        ],
    })
    await send({"type": "http.response.body", "body": raw})


# ── Toolkit Registry ────────────────────────────────────────────
toolkit_manager = ToolkitManager(str(PROJECT_DIR))

# All toolkit tools are indexed by (toolkit_name, tool_name) → handler
_TOOL_REGISTRY: dict[str, dict[str, tuple]] = {}  # toolkit_name → {tool_name: (handler, desc, params)}

COMMON_TOOLS = {"toolkit_list", "toolkit_switch", "toolkit_current", "exec_tool"}


def _build_tool_registry():
    """Build the handler registry from all discovered toolkits."""
    for tk_name, tk in toolkit_manager._toolkits.items():
        tools = {}
        for entry in tk.get_tools():
            fn, name, desc = entry[0], entry[1], entry[2]
            params = entry[3] if len(entry) > 3 else None
            tools[name] = (fn, desc, params)
        _TOOL_REGISTRY[tk_name] = tools


# Duplicate tool names across toolkits (computed once at startup)
_DUPES: set[str] = set()


def _detect_duplicate_names():
    """Compute tool names that appear in more than one toolkit. Call once after _build_tool_registry()."""
    from collections import Counter
    name_counts: Counter[str] = Counter()
    for tools in _TOOL_REGISTRY.values():
        for tool_name in tools:
            name_counts[tool_name] += 1
    _DUPES.update(name for name, cnt in name_counts.items() if cnt > 1)
    if _DUPES:
        log.info("duplicate tool names detected (will be prefixed): %s", sorted(_DUPES))


def _register_all_tools_static():
    """Register all toolkit tools as MCP tools with tags, then globally disable them."""
    for tk_name, tools in _TOOL_REGISTRY.items():
        tag = f"toolkit:{tk_name}"
        for tool_name, (handler, desc, params) in tools.items():
            # Create a wrapper that dispatches to the correct handler
            _register_single_tool(tk_name, tool_name, handler, desc, params, tag)

    # Globally disable all toolkit tools — they'll be enabled per-session
    for tk_name in _TOOL_REGISTRY:
        mcp.disable(tags={f"toolkit:{tk_name}"})


def _registered_name(tk_name: str, tool_name: str) -> str:
    """Return the MCP-registered tool name (with prefix if duplicated across toolkits)."""
    return f"{tk_name}__{tool_name}" if tool_name in _DUPES else tool_name


def _tool_list_for_toolkit(tk_name: str) -> list[str]:
    """Return list of MCP-registered names for a toolkit's tools (plus common tools)."""
    names = [_registered_name(tk_name, n) for n in _TOOL_REGISTRY[tk_name]]
    return sorted(set(names) | COMMON_TOOLS)


def _register_single_tool(tk_name: str, tool_name: str, handler, desc: str, params, tag: str):
    """Register a single toolkit tool with the MCP server."""
    # For duplicate names across toolkits, prefix with toolkit name
    reg_name = f"{tk_name}__{tool_name}" if tool_name in _DUPES else tool_name

    # Build parameter info for the wrapper function signature
    if params is None:
        params = BaseToolkit._extract_params(handler)

    # Create dynamic wrapper with proper signature
    sig_params = []
    defaults = {}
    annotations = {}
    for pname, ptype, pdefault, pdesc in params:
        sig_params.append(pname)
        if pdefault is not None:
            defaults[pname] = pdefault
        # Map type strings to actual Python types
        type_map = {
            "str": str, "int": int, "float": float, "bool": bool,
            "Optional[str]": Optional[str], "Optional[int]": Optional[int],
            "Optional[float]": Optional[float],
        }
        annotations[pname] = type_map.get(ptype, str)

    # Build the wrapper function dynamically
    import functools

    _tk_name = tk_name
    _tool_name = tool_name
    _handler = handler

    async def _wrapper(*args, **kwargs):
        # Call the original handler
        result = _handler(**kwargs)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return result

    # Set up the function signature for MCP introspection
    from inspect import Parameter, Signature

    # Build params: required first, then optional (avoids "non-default follows default" error)
    sig_params_obj = []
    optional_params = []
    for pname in sig_params:
        p = Parameter(
            pname,
            Parameter.POSITIONAL_OR_KEYWORD,
            default=defaults.get(pname, Parameter.empty),
            annotation=annotations.get(pname, Parameter.empty),
        )
        if defaults.get(pname, Parameter.empty) is Parameter.empty:
            sig_params_obj.append(p)
        else:
            optional_params.append(p)
    sig_params_obj.extend(optional_params)

    _wrapper.__signature__ = Signature(sig_params_obj)
    _wrapper.__annotations__ = annotations
    _wrapper.__name__ = reg_name
    _wrapper.__qualname__ = reg_name
    _wrapper.__doc__ = desc

    # Register with MCP using tags for per-session visibility
    mcp.tool(name=reg_name, description=desc, tags={tag})(_wrapper)


# ── Common Tools ────────────────────────────────────────────────

@mcp.tool()
def toolkit_list() -> str:
    """List all available toolkits.

    Returns a JSON object with a "toolkits" key containing a list of toolkit info objects.
    Each toolkit object includes "name", "description", and other metadata fields.

    Use this to discover which toolkits are available before calling toolkit_switch.

    Example response:
        {"toolkits": [{"name": "droid", "description": "Android device control"}, ...]}
    """
    return json.dumps({"toolkits": toolkit_manager.list_toolkits()})


@mcp.tool()
async def toolkit_switch(name: str, config: str = "{}", ctx: Context = CurrentContext()) -> str:
    """Switch to a toolkit. Tool list updates automatically after switching.

    Args:
        name: The toolkit name to switch to. Use toolkit_list to see available names.
        config: Optional JSON string for toolkit-specific configuration.
                Default is "{}". Some toolkits require config (e.g. workspace path).

    After switching, the toolkit's tools become available via exec_tool.
    Returns JSON with "status", "to" (toolkit name), "available_tools" list,
    and "tools_schema" describing each tool's parameters.

    If the toolkit is not found, returns an "error" with "available" names.
    """
    try:
        cfg = json.loads(config) if isinstance(config, str) else config
    except json.JSONDecodeError:
        cfg = {}

    if name not in _TOOL_REGISTRY:
        return json.dumps({
            "error": f"Toolkit '{name}' not found",
            "available": list(_TOOL_REGISTRY.keys()),
        })

    # Per-session: disable old toolkit, enable new one
    old = await ctx.get_state("current_toolkit")
    if old and old != name:
        await ctx.disable_components(tags={f"toolkit:{old}"})
    await ctx.enable_components(tags={f"toolkit:{name}"})
    await ctx.set_state("current_toolkit", name)

    # Build result info from registry
    tk = toolkit_manager._toolkits[name]
    tools_schema = tk._build_tools_schema()
    available_tools = _tool_list_for_toolkit(name)

    result = {
        "status": "switched",
        "from": old,
        "to": name,
        "toolkit": tk.get_info(),
        "available_tools": available_tools,
        "tools_schema": tools_schema,
    }

    if cfg:
        result["config_applied"] = cfg

    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def toolkit_current(ctx: Context = CurrentContext()) -> str:
    """Show the current active toolkit and its available tools.

    Returns JSON with "current" (toolkit name or null), "toolkit" (info object),
    and "available_tools" (list of tool names).

    If no toolkit is active, "current" is null and a "hint" field suggests
    using toolkit_switch to select one.
    """
    current_name = await ctx.get_state("current_toolkit")

    if not current_name:
        return json.dumps({
            "current": None,
            "toolkit": None,
            "hint": "Use toolkit_switch to switch to a target toolkit",
        })

    tk = toolkit_manager._toolkits.get(current_name)
    if not tk:
        return json.dumps({
            "current": None,
            "error": f"Previously active toolkit '{current_name}' not found",
        })

    info = {
        "current": current_name,
        "toolkit": tk.get_info(),
        "available_tools": _tool_list_for_toolkit(current_name),
    }
    return json.dumps(info, ensure_ascii=False)


@mcp.tool()
async def exec_tool(name: str, params: str = "{}", ctx: Context = CurrentContext()) -> str:
    """Execute a tool in the current toolkit. Pass the tool name and parameters as JSON string.

    Args:
        name: The tool name to execute (as returned by toolkit_switch's available_tools).
              Both plain names ("start_session") and prefixed names ("droid__start_session")
              are accepted.
        params: JSON string of keyword arguments for the tool.
                Default is "{}" (no arguments). Check tools_schema from toolkit_switch
                for each tool's expected parameters.

    A toolkit must be active (via toolkit_switch) before calling this.
    Returns the tool's result as JSON string, or an "error" if the tool is not found
    or no toolkit is active.
    """
    # Find which toolkit is active for this session
    toolkit_name = await ctx.get_state("current_toolkit")

    if not toolkit_name or toolkit_name not in _TOOL_REGISTRY:
        return json.dumps({
            "error": "No active toolkit. Use toolkit_switch first.",
        })

    tools = _TOOL_REGISTRY[toolkit_name]

    # Accept both raw name and prefixed name (e.g. "start_session" or "droid__start_session")
    resolved = name
    if name not in tools:
        # Try stripping the toolkit prefix
        prefix = f"{toolkit_name}__"
        if name.startswith(prefix):
            resolved = name[len(prefix):]

    if resolved not in tools:
        return json.dumps({
            "error": f"Tool '{name}' not found in toolkit '{toolkit_name}'",
            "available_tools": list(tools.keys()),
        })

    handler, _, _ = tools[resolved]

    try:
        args = json.loads(params) if isinstance(params, str) else params
        result = handler(**args)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return result
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON params: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Startup ─────────────────────────────────────────────────────

_build_tool_registry()
_detect_duplicate_names()
_register_all_tools_static()
toolkit_manager.startup_all()
log.info("startup complete, %d toolkits, %d tools registered",
         len(toolkit_manager._toolkits), sum(len(v) for v in _TOOL_REGISTRY.values()))

# ── Top-level ASGI app (for import by external runners / tests) ──
app = mcp.http_app(path="/mcp", json_response=True)


def _shutdown():
    log.info("shutdown started")
    toolkit_manager.shutdown_all()
    log.info("shutdown complete")


import atexit
atexit.register(_shutdown)

import signal as _signal
_signal.signal(_signal.SIGTERM, lambda *_: (_shutdown(), exit(0)))


def main():
    """CLI entry point."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Jenny MCP Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=31415)
    args = parser.parse_args()

    # Build Starlette app with auth middleware if password is set
    middleware = [(_AuthHeaders, (), {})] if MCP_PASSWORD else None
    app = mcp.http_app(path="/mcp", middleware=middleware, json_response=True)

    if MCP_PASSWORD:
        log.info("Auth middleware mounted")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
