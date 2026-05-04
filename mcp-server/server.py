"""
Tools MCP Server

支持动态工具包切换，切换时工具列表自动更新。

通用工具（始终可见）:
  - toolkit_list: 列出可用工具包
  - toolkit_switch: 切换工具包
  - toolkit_current: 显示当前工具包

Droid / Opencode 工具包:
  - start_session / send_message / poll_output / check_status / stop_session / exec_and_wait
  - Opencode 额外: cleanup

启动: python server.py [--host 0.0.0.0] [--port 31415]
"""

import inspect
import json
import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from toolkits import (
    ToolkitManager,
    OpencodeToolkit,
    DataAnalysisToolkit,
    WebEnhancedToolkit,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = PROJECT_DIR / "sessions"
WORKSPACE_DIR = PROJECT_DIR / "workspace"
CONFIG_PATH = PROJECT_DIR / "config" / "defaults.json"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("tools", json_response=True)

from mcp.server.transport_security import TransportSecuritySettings

# 允许的主机和来源，通过环境变量 ALLOWED_HOSTS 配置
# 默认仅允许本地访问，生产环境请按需配置
# 示例: export ALLOWED_HOSTS="10.1.*.*,192.168.*.*,127.0.0.1:*,localhost:*"
_allowed = os.environ.get("ALLOWED_HOSTS", "127.0.0.1:*,localhost:*").split(",")
_allowed_origins = [f"http://{h}" for h in _allowed]
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=_allowed,
    allowed_origins=_allowed_origins,
)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


toolkit_manager = ToolkitManager(
    sessions_dir=str(SESSIONS_DIR),
    workspace_dir=str(WORKSPACE_DIR),
    default_config=load_config(),
)

COMMON_TOOLS = {"toolkit_list", "toolkit_switch", "toolkit_current"}

_registered_tools: set[str] = set()

TYPE_MAP = {
    "str": str,
    "int": int,
    "Optional[str]": Optional[str],
    "Optional[int]": Optional[int],
}


# ============================================================
# 路由注册表：toolkit -> tool_name -> (handler, description, params)
# ============================================================

_TOOL_REGISTRY: dict[str, dict[str, tuple]] = {}


def _reg(toolkit: str, name: str, description: str, params: list):
    """工具路由注册装饰器，每个工具函数直接绑定到路由表"""

    def decorator(fn):
        _TOOL_REGISTRY.setdefault(toolkit, {})[name] = (fn, description, params)
        return fn

    return decorator


# ============================================================
# Droid 工具
# ============================================================


@_reg(
    "droid",
    "start_session",
    "启动一个 Droid 会话。Droid 通过文件管道与 AI 编程代理通信，支持完整的工具链（文件读写、终端执行、搜索等）。",
    [
        (
            "model",
            "Optional[str]",
            None,
            "模型 ID，如 custom:gpt-4o，不传用默认",
        ),
        ("auto_level", "str", "high", "自动级别 low/medium/high"),
        ("cwd", "Optional[str]", None, "工作目录，不传用默认 workspace"),
        ("session_id", "Optional[str]", None, "恢复已有会话的 ID"),
    ],
)
async def droid_start_session(
    model: Optional[str] = None,
    auto_level: str = "high",
    cwd: Optional[str] = None,
    session_id: Optional[str] = None,
    **_,
) -> dict:
    config = {
        "model": model,
        "auto_level": auto_level,
        "cwd": cwd,
        "workdir": cwd,
        "session_id": session_id,
    }
    return await toolkit_manager.get().start_session(config)


@_reg(
    "droid",
    "send_message",
    "向 Droid 会话发送消息，消息写入管道后由 AI 代理异步处理。发送后需用 poll_output 轮询结果。",
    [
        ("session_id", "str", None, "会话 ID"),
        ("message", "str", None, "消息内容，即发给 AI 代理的任务描述"),
    ],
)
async def droid_send_message(session_id: str, message: str, **_) -> dict:
    return await toolkit_manager.get().send_message(session_id, message)


@_reg(
    "droid",
    "poll_output",
    "轮询 Droid 会话的输出。每次调用返回自 last_line 以来的新内容，用 total_lines 追踪已读位置。",
    [
        ("session_id", "str", None, "会话 ID"),
        ("last_line", "int", 0, "上次读取到的行号，首次传 0"),
    ],
)
async def droid_poll_output(session_id: str, last_line: int = 0, **_) -> dict:
    return await toolkit_manager.get().poll_output(session_id, last_line)


@_reg(
    "droid",
    "check_status",
    "查看会话状态。不传 session_id 则列出所有会话。",
    [
        ("session_id", "Optional[str]", None, "会话 ID"),
    ],
)
async def droid_check_status(session_id: Optional[str] = None, **_) -> dict:
    return await toolkit_manager.get().check_status(session_id)


@_reg(
    "droid",
    "stop_session",
    "停止指定会话。",
    [
        ("session_id", "str", None, "会话 ID"),
    ],
)
async def droid_stop_session(session_id: str, **_) -> dict:
    return await toolkit_manager.get().stop_session(session_id)


@_reg(
    "droid",
    "exec_and_wait",
    "一站式执行：自动创建会话 → 发送消息 → 等待完成 → 返回结果。适合一次性任务，无需手动管理会话和轮询。推荐优先使用此工具。",
    [
        ("message", "str", None, "任务描述，如'在 /tmp 下创建一个 hello.py 并运行'"),
        ("timeout", "int", 300, "超时秒数，默认 300"),
        ("cwd", "Optional[str]", None, "工作目录，不传用默认 workspace"),
    ],
)
async def droid_exec_and_wait(
    message: str, timeout: int = 300, cwd: Optional[str] = None, **_
) -> dict:
    config = {"cwd": cwd, "workdir": cwd}
    return await toolkit_manager.get().exec_and_wait(message, timeout, config)


# ============================================================
# Opencode 工具
# ============================================================


@_reg(
    "opencode",
    "start_session",
    "创建 OpenCode 会话。OpenCode 通过 HTTP API 与编程代理通信，自动启动后台 serve 进程。",
    [
        ("model", "str", "opencode/big-pickle", "模型 ID，格式: provider/model。免费模型: opencode/big-pickle, opencode/gpt-5-nano 等"),
        ("cwd", "Optional[str]", None, "工作目录，不传用默认 workspace"),
        ("port", "int", 4096, "服务器端口，不传用默认 4096"),
    ],
)
async def opencode_start_session(
    model: str = "opencode/big-pickle", cwd: Optional[str] = None, port: int = 4096, **_
) -> dict:
    config = {"model": model, "workdir": cwd, "cwd": cwd, "port": port}
    return await toolkit_manager.get().start_session(config)


@_reg(
    "opencode",
    "send_message",
    "向 OpenCode 会话发送消息。异步模式：如果 AI 响应快则直接返回，否则自动轮询等待结果（最多 120 秒）。",
    [
        ("session_id", "str", None, "会话 ID"),
        ("message", "str", None, "消息内容，即发给 AI 代理的任务描述"),
    ],
)
async def opencode_send_message(session_id: str, message: str, **_) -> dict:
    return await toolkit_manager.get().send_message(session_id, message)


@_reg(
    "opencode",
    "poll_output",
    "获取 OpenCode 会话的消息列表。用于手动轮询 AI 代理的响应。",
    [
        ("session_id", "str", None, "会话 ID"),
        ("last_line", "int", 0, "上次读取到的行号，首次传 0"),
    ],
)
async def opencode_poll_output(session_id: str, last_line: int = 0, **_) -> dict:
    return await toolkit_manager.get().poll_output(session_id, last_line)


@_reg(
    "opencode",
    "check_status",
    "检查 Opencode 会话或服务器状态。",
    [
        ("session_id", "Optional[str]", None, "会话 ID，不传查看全局状态"),
    ],
)
async def opencode_check_status(session_id: Optional[str] = None, **_) -> dict:
    return await toolkit_manager.get().check_status(session_id)


@_reg(
    "opencode",
    "stop_session",
    "删除 Opencode 会话。",
    [
        ("session_id", "str", None, "会话 ID"),
    ],
)
async def opencode_stop_session(session_id: str, **_) -> dict:
    return await toolkit_manager.get().stop_session(session_id)


@_reg(
    "opencode",
    "exec_and_wait",
    "一站式执行：自动创建会话 → 发送消息 → 等待 AI 响应 → 返回结果。适合一次性任务，推荐优先使用。",
    [
        ("message", "str", None, "任务描述，如'读取 /tmp/data.csv 的前 5 行'"),
        ("timeout", "int", 300, "超时秒数，默认 300"),
        ("cwd", "Optional[str]", None, "工作目录，不传用默认 workspace"),
    ],
)
async def opencode_exec_and_wait(
    message: str, timeout: int = 300, cwd: Optional[str] = None, **_
) -> dict:
    config = {"workdir": cwd, "cwd": cwd}
    return await toolkit_manager.get().exec_and_wait(message, timeout, config)


@_reg("opencode", "cleanup", "清理 Opencode 资源（停止服务器）。", [])
async def opencode_cleanup(**_) -> dict:
    toolkit = toolkit_manager._toolkits.get("opencode")
    if toolkit and isinstance(toolkit, OpencodeToolkit):
        return await toolkit.cleanup()
    return {"error": "Opencode toolkit not available"}


# ============================================================
# Data Analysis 工具
# ============================================================


@_reg(
    "data_analysis",
    "csv_info",
    "获取 CSV 文件基本信息（行数、列名、类型、缺失值统计）。",
    [
        ("file_path", "str", None, "CSV 文件路径"),
        ("encoding", "str", "utf-8", "文件编码"),
    ],
)
async def data_analysis_csv_info(file_path: str, encoding: str = "utf-8", **_) -> dict:
    return await toolkit_manager.get().csv_info(file_path, encoding)


@_reg(
    "data_analysis",
    "csv_analyze",
    "对 CSV 指定列做统计分析（均值、中位数、分位数、分布等）。",
    [
        ("file_path", "str", None, "CSV 文件路径"),
        ("columns", "Optional[str]", None, "要分析的列，逗号分隔"),
        ("group_by", "Optional[str]", None, "分组列名"),
        ("agg", "str", "mean", "聚合方式 mean/sum/count/min/max/std/median"),
        ("encoding", "str", "utf-8", "文件编码"),
    ],
)
async def data_analysis_csv_analyze(
    file_path: str,
    columns: Optional[str] = None,
    group_by: Optional[str] = None,
    agg: str = "mean",
    encoding: str = "utf-8",
    **_,
) -> dict:
    return await toolkit_manager.get().csv_analyze(
        file_path, columns, group_by, agg, encoding
    )


@_reg(
    "data_analysis",
    "csv_query",
    "用 pandas 表达式筛选/过滤/排序 CSV 数据。支持 SQL 风格的查询。",
    [
        ("file_path", "str", None, "CSV 文件路径"),
        ("select", "str", "*", "返回列，逗号分隔，如 'name,age,score'"),
        ("where", "Optional[str]", None, "过滤表达式，如 'age > 18 and score >= 60'"),
        ("order_by", "Optional[str]", None, "排序列，加前缀 desc 表示降序，如 'score desc'"),
        ("limit", "int", 100, "返回行数上限"),
        ("encoding", "str", "utf-8", "文件编码"),
    ],
)
async def data_analysis_csv_query(
    file_path: str,
    select: str = "*",
    where: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 100,
    encoding: str = "utf-8",
    **_,
) -> dict:
    return await toolkit_manager.get().csv_query(
        file_path, select, where, order_by, limit, encoding
    )


@_reg(
    "data_analysis",
    "csv_chart",
    "用 matplotlib 生成图表并保存为 PNG。支持折线/柱状/散点/饼/直方图。",
    [
        ("file_path", "str", None, "CSV 文件路径"),
        ("chart_type", "str", None, "图表类型: line(折线)/bar(柱状)/scatter(散点)/pie(饼)/hist(直方)"),
        ("x", "str", None, "X 轴列名"),
        ("y", "Optional[str]", None, "Y 轴列名（pie/hist 可不传）"),
        ("title", "Optional[str]", None, "图表标题"),
        ("limit", "int", 500, "最大数据点数"),
        ("encoding", "str", "utf-8", "文件编码"),
    ],
)
async def data_analysis_csv_chart(
    file_path: str,
    chart_type: str,
    x: str,
    y: Optional[str] = None,
    title: Optional[str] = None,
    limit: int = 500,
    encoding: str = "utf-8",
    **_,
) -> dict:
    return await toolkit_manager.get().csv_chart(
        file_path, chart_type, x, y, title, limit, encoding
    )


@_reg(
    "data_analysis",
    "json_query",
    "解析 JSON 文件，支持字典路径查询。",
    [
        ("file_path", "str", None, "JSON 文件路径"),
        ("path", "str", ".", "查询路径"),
        ("pretty", "bool", True, "是否格式化输出"),
        ("encoding", "str", "utf-8", "文件编码"),
    ],
)
async def data_analysis_json_query(
    file_path: str,
    path: str = ".",
    pretty: bool = True,
    encoding: str = "utf-8",
    **_,
) -> dict:
    return await toolkit_manager.get().json_query(file_path, path, pretty, encoding)


# ============================================================
# Web Enhanced 工具
# ============================================================


@_reg(
    "web_enhanced",
    "web_fetch_js",
    "用 Playwright 无头浏览器渲染页面（执行 JS），提取正文内容。适合需要 JS 渲染的动态网页。",
    [
        ("url", "str", None, "目标网页 URL"),
        ("selector", "Optional[str]", None, "CSS 选择器，只提取匹配元素的内容"),
        ("wait_for", "Optional[str]", None, "等待某个 CSS 选择器出现后再提取"),
        ("timeout", "int", 30, "超时秒数"),
        ("extract_links", "bool", False, "是否同时提取页面中的链接"),
        ("cookies_file", "Optional[str]", None, "预先用 web_login 保存的 cookies 文件路径"),
    ],
)
async def web_enhanced_fetch_js(
    url: str,
    selector: Optional[str] = None,
    wait_for: Optional[str] = None,
    timeout: int = 30,
    extract_links: bool = False,
    cookies_file: Optional[str] = None,
    **_,
) -> dict:
    return await toolkit_manager.get().web_fetch_js(
        url, selector, wait_for, timeout, extract_links, cookies_file
    )


@_reg(
    "web_enhanced",
    "web_batch_fetch",
    "批量并发抓取多个 URL 的内容，比逐个抓取更高效。",
    [
        ("urls", "str", None, "URL 列表，JSON 数组字符串如 '[\"https://a.com\",\"https://b.com\"]' 或逗号分隔"),
        ("timeout", "int", 30, "单个请求超时秒数"),
        ("max_concurrent", "int", 5, "最大并发数"),
        ("extract_text", "bool", True, "是否提取纯文本（false 则返回原始 HTML）"),
    ],
)
async def web_enhanced_batch_fetch(
    urls: str,
    timeout: int = 30,
    max_concurrent: int = 5,
    extract_text: bool = True,
    **_,
) -> dict:
    return await toolkit_manager.get().web_batch_fetch(
        urls, timeout, max_concurrent, extract_text
    )


@_reg(
    "web_enhanced",
    "web_search_enhanced",
    "增强搜索：在普通搜索基础上支持时间范围、站点限定、摘要提取。返回结果比普通搜索更丰富。",
    [
        ("query", "str", None, "搜索关键词"),
        ("num_results", "int", 10, "返回结果数量，最大 20"),
        ("time_range", "Optional[str]", None, "时间范围过滤: day(一天内)/week(一周内)/month(一月内)/year(一年内)"),
        ("site", "Optional[str]", None, "限定站点域名，如 'github.com'"),
        ("extract_snippets", "bool", True, "是否提取搜索结果的摘要文本"),
    ],
)
async def web_enhanced_search(
    query: str,
    num_results: int = 10,
    time_range: Optional[str] = None,
    site: Optional[str] = None,
    extract_snippets: bool = True,
    **_,
) -> dict:
    return await toolkit_manager.get().web_search_enhanced(
        query, num_results, time_range, site, extract_snippets
    )


@_reg(
    "web_enhanced",
    "web_login",
    "用 Playwright 浏览器自动登录网站并保存 cookies。保存后可用 web_fetch_js 的 cookies_file 参数访问需要登录的页面。",
    [
        ("url", "str", None, "登录页面 URL"),
        ("username_selector", "str", None, "用户名输入框的 CSS 选择器，如 '#username' 或 'input[name=email]'"),
        ("password_selector", "str", None, "密码输入框的 CSS 选择器，如 '#password' 或 'input[type=password]'"),
        ("username", "str", None, "用户名/邮箱"),
        ("password", "str", None, "密码"),
        ("submit_selector", "Optional[str]", None, "提交按钮的 CSS 选择器，如 'button[type=submit]'"),
        ("cookies_file", "Optional[str]", None, "Cookies 保存路径，如 '/tmp/cookies_github.json'"),
        ("wait_after_login", "int", 3, "点击登录后等待秒数"),
        ("verify_selector", "Optional[str]", None, "登录成功后页面上应出现的元素的 CSS 选择器，用于验证登录是否成功"),
    ],
)
async def web_enhanced_login(
    url: str,
    username_selector: str,
    password_selector: str,
    username: str,
    password: str,
    submit_selector: Optional[str] = None,
    cookies_file: Optional[str] = None,
    wait_after_login: int = 3,
    verify_selector: Optional[str] = None,
    **_,
) -> dict:
    return await toolkit_manager.get().web_login(
        url,
        username_selector,
        password_selector,
        username,
        password,
        submit_selector,
        cookies_file,
        wait_after_login,
        verify_selector,
    )


# ============================================================
# 动态注册/注销
# ============================================================


def _unregister_toolkit_tools():
    """移除当前所有非通用工具"""
    tm = mcp._tool_manager
    for name in list(_registered_tools):
        if name in tm._tools:
            tm.remove_tool(name)
    _registered_tools.clear()


def _get_tools_schema(toolkit_name: str) -> list[dict]:
    """获取工具包的完整 schema"""
    tools = _TOOL_REGISTRY.get(toolkit_name, {})
    schemas = []
    for name, (handler, description, params) in tools.items():
        param_schemas = []
        for pname, ptype_str, pdefault, pdoc in params:
            param_schemas.append(
                {
                    "name": pname,
                    "type": ptype_str,
                    "description": pdoc,
                }
            )
        schemas.append(
            {
                "name": name,
                "description": description,
                "parameters": param_schemas,
            }
        )
    return schemas


def _register_toolkit_tools(toolkit_name: str):
    """从路由表注册指定工具包的工具"""
    tm = mcp._tool_manager
    tools = _TOOL_REGISTRY.get(toolkit_name, {})

    for name, (handler, description, params) in tools.items():
        # 每个 handler 都是独立的函数引用，无闭包问题
        def _bind(fn):
            async def wrapper(**kwargs):
                return json.dumps(await fn(**kwargs))

            return wrapper

        wrapper = _bind(handler)

        # 构建签名
        sig_params = []
        for pname, ptype_str, pdefault, _pdoc in params:
            ann = TYPE_MAP.get(ptype_str, str)
            if pdefault is None and not ptype_str.startswith("Optional"):
                p = inspect.Parameter(
                    pname, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ann
                )
            else:
                p = inspect.Parameter(
                    pname,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=pdefault,
                    annotation=ann,
                )
            sig_params.append(p)
        wrapper.__signature__ = inspect.Signature(sig_params)

        param_docs = "\n".join(f"        {p[0]}: {p[3]}" for p in params)
        wrapper.__doc__ = (
            f"{description}\n\nArgs:\n{param_docs}" if params else description
        )
        wrapper.__name__ = name

        tm.add_tool(wrapper, name=name, description=wrapper.__doc__)
        _registered_tools.add(name)


# ============================================================
# 通用执行器（支持热注册）
# ============================================================


@mcp.tool()
def exec_tool(name: str, params: str = "{}") -> str:
    """执行当前工具包中的任意工具。切换工具包后，新工具可能尚未出现在工具列表中，此时用 exec_tool 作为通用入口调用。

    常用流程：
    1. toolkit_switch 切换到目标工具包
    2. 用 exec_tool 调用新工具包的工具，例如 exec_tool("csv_info", '{"file_path": "/tmp/data.csv"}')

    Args:
        name: 工具名称，如 start_session、csv_info、web_fetch_js 等
        params: JSON 格式的参数字符串，如 '{"file_path": "/tmp/data.csv"}'

    Returns:
        工具执行结果的 JSON 字符串
    """
    import asyncio

    toolkit_name = toolkit_manager._current
    tools = _TOOL_REGISTRY.get(toolkit_name, {})

    if name not in tools:
        return json.dumps(
            {
                "error": f"Tool '{name}' not found in toolkit '{toolkit_name}'",
                "available_tools": list(tools.keys()),
            }
        )

    handler, _, _ = tools[name]

    try:
        args = json.loads(params) if isinstance(params, str) else params
        result = asyncio.get_event_loop().run_until_complete(handler(**args))
        return json.dumps(result)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON params: {e}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# 通用工具（始终可见）
# ============================================================


@mcp.tool()
def toolkit_list() -> str:
    """列出所有可用的工具包。

    Returns:
        工具包列表，包含名称、描述和工具清单
    """
    return json.dumps({"toolkits": toolkit_manager.list_toolkits()})


@mcp.tool()
def toolkit_switch(name: str, config: str = "{}") -> str:
    """切换当前工具包。切换后工具列表自动更新，下一轮对话即可使用新工具。

    可用工具包：
    - "droid": Droid 文件管道模式，适合需要完整工具链的编程任务
    - "opencode": OpenCode HTTP API 模式，适合多轮交互式编程
    - "data_analysis": 数据分析，支持 CSV/JSON 查询、统计、图表生成
    - "web_enhanced": 增强网络操作，支持 JS 渲染、批量抓取、登录、增强搜索

    切换后推荐直接用 exec_and_wait 一站式执行，或用 exec_tool 调用任意工具。

    Args:
        name: 工具包名称，可选 "droid"、"opencode"、"data_analysis"、"web_enhanced"
        config: JSON 配置参数（可选），示例：
            Droid: '{"model": "custom:your-model", "auto_level": "high", "cwd": "/path"}'
            Opencode: '{"model": "opencode/big-pickle", "workdir": "/path"}'

    Returns:
        切换结果、新工具列表和完整 schema
    """
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
    """显示当前工具包。

    Returns:
        当前工具包名称和可用工具
    """
    info = toolkit_manager.current()
    info["available_tools"] = sorted(_registered_tools | COMMON_TOOLS)
    return json.dumps(info)


# ============================================================
# 启动
# ============================================================

_register_toolkit_tools(toolkit_manager._current)


def _startup_cleanup():
    """启动时清理 droid 孤儿会话并启动 GC"""
    import asyncio as _aio
    droid = toolkit_manager._toolkits.get("droid")
    if droid and hasattr(droid, "cleanup_orphan_sessions"):
        try:
            loop = _aio.get_event_loop()
            if loop.is_running():
                _aio.ensure_future(droid.cleanup_orphan_sessions())
            else:
                loop.run_until_complete(droid.cleanup_orphan_sessions())
            print("[startup] Droid orphan sessions cleaned")
        except RuntimeError:
            _aio.ensure_future(droid.cleanup_orphan_sessions())
    if droid and hasattr(droid, "start_gc"):
        droid.start_gc()
        print("[startup] Droid GC started (idle timeout: 30min)")
    # opencode GC
    opencode = toolkit_manager._toolkits.get("opencode")
    if opencode and hasattr(opencode, "start_gc"):
        opencode.start_gc()
        print("[startup] Opencode GC started (idle timeout: 30min, auto-stop serve)")


_startup_cleanup()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tools MCP Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=31415)
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = "/mcp"
    mcp.run(transport="streamable-http")
