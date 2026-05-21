import inspect
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

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
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)] %(message)s"))
_handler.setLevel(logging.INFO)

logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("toolkits").setLevel(logging.DEBUG)

log = logging.getLogger("mcp-server")

mcp = FastMCP("tools", json_response=True)

from mcp.server.transport_security import TransportSecuritySettings

mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=["10.1.*.*", "192.168.*.*", "127.0.0.1:*", "localhost:*"],
    allowed_origins=[
        "http://10.1.*.*",
        "http://192.168.*.*",
        "http://127.0.0.1:*",
        "http://localhost:*",
    ],
)

toolkit_manager = ToolkitManager(base_dir=str(PROJECT_DIR))
log.info("base_dir=%s", PROJECT_DIR)

COMMON_TOOLS = {"toolkit_list", "toolkit_switch", "toolkit_current"}

_registered_tools: set[str] = set()

TYPE_MAP = {
    "str": str,
    "int": int,
    "bool": bool,
    "float": float,
    "Optional[str]": Optional[str],
    "Optional[int]": Optional[int],
    "Optional[float]": Optional[float],
}

_TOOL_REGISTRY: dict[str, dict[str, tuple]] = {}


def _unregister_toolkit_tools():
    tm = mcp._tool_manager
    for name in list(_registered_tools):
        try:
            if name in tm._tools:
                tm.remove_tool(name)
        except Exception:
            pass
    _registered_tools.clear()


def _auto_discover_tools():
    for tk_name, tk_instance in toolkit_manager._toolkits.items():
        if tk_name in _TOOL_REGISTRY:
            continue
        for entry in tk_instance.get_tools():
            fn, tool_name, desc = entry[0], entry[1], entry[2]
            params = entry[3] if len(entry) > 3 else BaseToolkit._extract_params(fn)
            _TOOL_REGISTRY.setdefault(tk_name, {})[tool_name] = (fn, desc, params)


def _get_tools_schema(toolkit_name: str) -> list[dict]:
    tools = _TOOL_REGISTRY.get(toolkit_name, {})
    schemas = []
    for name, (handler, description, params) in tools.items():
        param_schemas = []
        for pname, ptype_str, pdefault, pdoc in params:
            param_schemas.append(
                {"name": pname, "type": ptype_str, "description": pdoc}
            )
        schemas.append({"name": name, "description": description, "parameters": param_schemas})
    return schemas


def _register_toolkit_tools(toolkit_name: str):
    tm = mcp._tool_manager
    tools = _TOOL_REGISTRY.get(toolkit_name, {})

    for name, (handler, description, params) in tools.items():
        try:
            if name in tm._tools:
                tm.remove_tool(name)
        except Exception:
            pass

        def _bind(fn):
            async def wrapper(**kwargs):
                return json.dumps(await fn(**kwargs))
            return wrapper

        wrapper = _bind(handler)

        sig_params = []
        for pname, ptype_str, pdefault, _pdoc in params:
            ann = TYPE_MAP.get(ptype_str, str)
            if pdefault is None and not ptype_str.startswith("Optional"):
                p = inspect.Parameter(
                    pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ann
                )
            else:
                p = inspect.Parameter(
                    pname, inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=pdefault, annotation=ann,
                )
            sig_params.append(p)

        has_default = False
        fixed_params = []
        for p in sig_params:
            if p.default is not inspect.Parameter.empty:
                has_default = True
            elif has_default:
                p = p.replace(default=None)
            fixed_params.append(p)

        wrapper.__signature__ = inspect.Signature(fixed_params)
        param_docs = "\n".join(f"        {p[0]}: {p[3]}" for p in params)
        wrapper.__doc__ = f"{description}\n\nArgs:\n{param_docs}" if params else description
        wrapper.__name__ = name

        tm.add_tool(wrapper, name=name, description=wrapper.__doc__)
        _registered_tools.add(name)


@mcp.tool()
async def exec_tool(name: str, params: str = "{}") -> str:
    """Execute any tool in the current toolkit. Use after toolkit_switch when new tools are not yet in the tool list."""
    toolkit_name = toolkit_manager._current

    if toolkit_name is None:
        return json.dumps({
            "error": "No toolkit selected, use toolkit_switch first",
            "available_toolkits": list(toolkit_manager._toolkits.keys()),
        })

    tools = _TOOL_REGISTRY.get(toolkit_name, {})

    if name not in tools:
        return json.dumps({
            "error": f"Tool '{name}' not found in toolkit '{toolkit_name}'",
            "available_tools": list(tools.keys()),
        })

    handler, _, _ = tools[name]

    try:
        args = json.loads(params) if isinstance(params, str) else params
        result = await handler(**args)
        return json.dumps(result)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON params: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def toolkit_list() -> str:
    """List all available toolkits."""
    return json.dumps({"toolkits": toolkit_manager.list_toolkits()})


@mcp.tool()
def toolkit_switch(name: str, config: str = "{}") -> str:
    """Switch to a toolkit. Tool list updates automatically after switching."""
    try:
        cfg = json.loads(config) if isinstance(config, str) else config
    except json.JSONDecodeError:
        cfg = {}

    _unregister_toolkit_tools()
    result = toolkit_manager.switch(name, cfg)
    _register_toolkit_tools(name)

    result["available_tools"] = sorted(_registered_tools | COMMON_TOOLS)
    result["tools_schema"] = _get_tools_schema(name)
    return json.dumps(result)


@mcp.tool()
def toolkit_current() -> str:
    """Show the current toolkit."""
    info = toolkit_manager.current()
    info["available_tools"] = sorted(_registered_tools | COMMON_TOOLS)
    return json.dumps(info)


_auto_discover_tools()
toolkit_manager.startup_all()
log.info("startup complete, %d toolkits, %d tools", len(toolkit_manager._toolkits), sum(len(v) for v in _TOOL_REGISTRY.values()))


def _shutdown():
    log.info("shutdown started")
    toolkit_manager.shutdown_all()
    log.info("shutdown complete")


import atexit
atexit.register(_shutdown)

import signal as _signal
_signal.signal(_signal.SIGTERM, lambda *_: (_shutdown(), exit(0)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Jenny MCP Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=31415)
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = "/mcp"
    mcp.run(transport="streamable-http")
