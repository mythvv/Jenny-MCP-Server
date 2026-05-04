# Jenny MCP Server

> 通过 MCP 协议（Model Context Protocol）统一调度 AI 编码代理、数据分析和网页抓取的轻量工具服务器。

Jenny MCP Server 是一个基于 [FastMCP](https://github.com/modelcontextprotocol/python-sdk) 的工具服务器，为 AI 助手提供可动态切换的工具包。它将 Droid、OpenCode 等编码代理以及数据分析、网页抓取能力封装为标准 MCP 工具，任何支持 MCP 协议的客户端都可以直接调用。

## ✨ 特性

- 🔄 **动态工具包切换** — 运行时一键切换工具包，工具列表自动更新
- 🤖 **多编码代理** — 支持 [Factory Droid](https://docs.factory.ai/)（文件管道）和 [OpenCode](https://opencode.ai/)（HTTP API）
- 📊 **数据分析** — CSV 查询/统计/可视化、JSON 路径查询
- 🌐 **网页抓取** — JS 渲染抓取、批量并发、增强搜索、浏览器登录
- ⏱ **会话管理** — 自动 GC、空闲超时回收、孤儿会话清理
- 📜 **Shell 脚本** — 附带 start/send/poll/status 脚本，可直接命令行交互

## 架构

```
┌──────────────────────────────────────────────────────┐
│                  MCP Client (任意)                     │
│          Claude / Jenny / Cursor / ...                │
└──────────────────────┬───────────────────────────────┘
                       │ MCP (Streamable HTTP)
                       │ :31415/mcp
┌──────────────────────▼───────────────────────────────┐
│                  MCP Server (FastMCP)                  │
│  ┌─────────────────────────────────────────────────┐  │
│  │              通用工具 (始终可见)                   │  │
│  │   toolkit_list / toolkit_switch / toolkit_current│  │
│  └─────────────────────┬───────────────────────────┘  │
│                        │ 动态切换                      │
│  ┌─────────┬───────────┼───────────┬──────────────┐   │
│  │  Droid  │ OpenCode  │DataAnalysis│ WebEnhanced │   │
│  │(管道模式)│(HTTP API) │(CSV/JSON) │(JS渲染抓取)  │   │
│  └────┬────┴─────┬─────┴─────┬─────┴──────┬──────┘   │
└───────┼──────────┼───────────┼────────────┼───────────┘
        │          │           │            │
   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌────▼─────┐
   │  Droid │ │OpenCode│ │Pandas  │ │Playwright│
   │  CLI   │ │ Serve  │ │+Mpl    │ │ +AIOHTTP │
   └────────┘ └────────┘ └────────┘ └──────────┘
```

### 会话模型

```
                    Droid（文件管道模式）
 ┌────────┐  input.jsonl   ┌──────────┐
 │ Client │ ──────────────►│  droid   │
 │        │  (JSON-RPC)    │  exec    │
 │        │◄────────────── │  (tail)  │
 └────────┘  output.jsonl  └──────────┘

                    OpenCode（HTTP API 模式）
 ┌────────┐   POST /session/{id}/message   ┌──────────┐
 │ Server │ ──────────────────────────────► │ opencode │
 │        │ ◄────────────────────────────── │  serve   │
 └────────┘   JSON response (同步等待)      └──────────┘
```

## 目录结构

```
jenny-mcp-server/
├── config/
│   └── defaults.example.json   # 配置模板
├── mcp-server/
│   ├── server.py               # MCP 服务器主入口 + 工具路由注册
│   ├── requirements.txt        # Python 依赖
│   └── toolkits/
│       ├── __init__.py         # 工具包导出
│       ├── base.py             # 抽象基类 BaseToolkit
│       ├── manager.py          # 工具包管理器 ToolkitManager
│       ├── droid.py            # Droid 工具包
│       ├── opencode.py         # OpenCode 工具包
│       ├── data_analysis.py    # 数据分析工具包
│       └── web_enhanced.py     # Web 增强工具包
├── scripts/
│   ├── start.sh                # 启动 Droid 会话
│   ├── send.sh                 # 向会话发送消息
│   ├── poll.sh                 # 轮询会话输出
│   └── status.sh               # 查看会话状态
├── sessions/                   # 会话数据（运行时生成）
├── workspace/                  # 代理工作目录（运行时生成）
└── README.md
```

## 安装

### 前置要求

- Python 3.11+
- [Factory Droid CLI](https://docs.factory.ai/)（仅 Droid 工具包需要）
- [OpenCode](https://opencode.ai/)（仅 OpenCode 工具包需要）

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/jenny-mcp-server.git
cd jenny-mcp-server

# 2. 创建虚拟环境并安装依赖
cd mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 额外依赖（按需安装）
pip install httpx          # OpenCode 工具包
pip install pandas matplotlib  # 数据分析工具包
pip install playwright aiohttp  # Web 增强工具包
playwright install chromium    # 安装浏览器

# 3. 创建配置文件
cp ../config/defaults.example.json ../config/defaults.json
# 编辑 defaults.json 填入实际配置
```

## 使用

### 启动服务器

```bash
cd mcp-server
source .venv/bin/activate

# 默认 0.0.0.0:31415
python server.py

# 自定义地址
python server.py --host 127.0.0.1 --port 8080
```

服务端点为 `http://<host>:<port>/mcp`（Streamable HTTP 传输）。

### 客户端配置

在 MCP 客户端的配置文件中添加：

```json
{
  "mcpServers": {
    "jenny-tools": {
      "url": "http://127.0.0.1:31415/mcp"
    }
  }
}
```

### Shell 脚本（Droid 直接交互）

```bash
# 启动新会话，返回 session-id
SESSION=$(./scripts/start.sh)
echo "Session: $SESSION"

# 发送消息
./scripts/send.sh "$SESSION" "Create a hello world Python script"

# 轮询输出
./scripts/poll.sh "$SESSION" 0    # 从第 0 行开始读取

# 查看所有会话状态
./scripts/status.sh

# 查看特定会话
./scripts/status.sh "$SESSION"
```

## API 文档

### 通用工具

这三个工具在任何工具包激活状态下都可用。

#### `toolkit_list`

列出所有可用工具包及其工具。

**参数：** 无

**返回示例：**

```json
{
  "toolkits": {
    "droid": { "description": "Factory Droid - 文件管道模式", "tools": [...] },
    "opencode": { "description": "OpenCode - HTTP API 多轮会话模式", "tools": [...] },
    "data_analysis": { "description": "数据分析工具包 - CSV 查询/统计/可视化", "tools": [...] },
    "web_enhanced": { "description": "Web Enhanced - JS 渲染抓取", "tools": [...] }
  }
}
```

#### `toolkit_switch`

切换当前工具包，工具列表自动更新。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 工具包名称：`droid` / `opencode` / `data_analysis` / `web_enhanced` |
| `config` | string | ❌ | JSON 配置参数 |

**config 参数说明：**

```jsonc
// Droid
{ "model": "custom:YOUR_MODEL", "auto_level": "high", "cwd": "/path/to/project" }

// OpenCode
{ "model": "opencode/big-pickle", "workdir": "/path/to/project" }
```

#### `toolkit_current`

显示当前工具包名称和可用工具列表。

---

### 🤖 Droid 工具包

通过文件管道（`tail -f input.jsonl | droid exec`）与 [Factory Droid](https://docs.factory.ai/) 交互。每个会话独立一个目录，支持多轮对话。

#### `start_session`

创建一个新的 Droid 会话。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config` | object | ❌ | 覆盖默认配置（model, auto_level, cwd 等） |

**返回：** `{ "session_id": "uuid", "status": "started", "pid": 12345, "session_dir": "/path" }`

#### `send_message`

向指定会话发送消息。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | 会话 ID |
| `message` | string | ✅ | 消息内容 |

#### `poll_output`

轮询会话输出，支持增量读取。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | 会话 ID |
| `last_line` | int | ❌ | 上次读取到的行号，仅返回此行之后的新内容 |

**返回：** `{ "lines": [...], "total_lines": 42 }`

#### `check_status`

检查会话状态。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | 会话 ID |

#### `stop_session`

停止并清理会话。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | 会话 ID |

#### `exec_and_wait`

一站式执行：创建会话 → 发送消息 → 等待完成 → 返回输出。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | ✅ | 要执行的消息 |
| `timeout` | int | ❌ | 超时秒数，默认 900（15分钟） |
| `config` | object | ❌ | 会话配置 |

---

### 🔮 OpenCode 工具包

通过 HTTP API 与 [OpenCode](https://opencode.ai/) 交互。自动管理 `opencode serve` 进程的生命周期。

#### `start_session`

启动 opencode serve 并创建会话。自动检测已有 serve 进程，按需启动。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config` | object | ❌ | `model`（如 `"opencode/big-pickle"`）、`workdir` |

#### `send_message`

向会话发送消息。OpenCode API 同步等待响应，直接返回结果。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | 会话 ID |
| `message` | string | ✅ | 消息内容 |

**返回：** `{ "response": "...", "reasoning": "...", "message_id": "..." }`

#### `poll_output`

获取会话消息列表（历史记录）。

#### `check_status`

检查 serve 进程和会话状态。

#### `stop_session`

删除远程会话。

#### `exec_and_wait`

一站式执行：创建会话 → 发送消息 → 返回响应。

#### `cleanup`

清理所有资源：删除全部会话、停止 serve 进程。

---

### 📊 Data Analysis 工具包

基于 Pandas + Matplotlib 的数据分析工具。

#### `csv_info`

获取 CSV 文件基本信息（行数、列名、类型、缺失值）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | ✅ | CSV 文件路径（支持相对路径，基于 workspace） |
| `encoding` | string | ❌ | 文件编码，默认 `utf-8` |

#### `csv_analyze`

CSV 数据统计分析（describe、分组聚合）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | ✅ | CSV 文件路径 |
| `operation` | string | ❌ | 操作：`describe` / `groupby`，默认 `describe` |
| `column` | string | ❌ | 目标列名 |
| `group_by` | string | ❌ | 分组列（groupby 时必填） |
| `agg_func` | string | ❌ | 聚合函数：`mean` / `sum` / `count` / `min` / `max`，默认 `mean` |

#### `csv_query`

使用 SQL 风格查询 CSV 数据（基于 Pandas DataFrame.query）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | ✅ | CSV 文件路径 |
| `query` | string | ✅ | 查询表达式，如 `"age > 30 & city == 'Beijing'"` |
| `columns` | string | ❌ | 选择列，逗号分隔，如 `"name,age,city"` |

#### `csv_chart`

CSV 数据可视化（生成图表保存为 PNG）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | ✅ | CSV 文件路径 |
| `chart_type` | string | ✅ | 图表类型：`line` / `bar` / `scatter` / `pie` |
| `x_column` | string | ✅ | X 轴列名 |
| `y_column` | string | ✅ | Y 轴列名（pie 图为数值列） |
| `title` | string | ❌ | 图表标题 |

**返回：** `{ "chart_path": "/tmp/data_analysis_charts/chart_xxx.png", "data_points": 100 }`

#### `json_query`

JSON 文件路径查询。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | ✅ | JSON 文件路径 |
| `path` | string | ❌ | 查询路径，如 `users[0].name`，默认 `.`（根） |
| `pretty` | bool | ❌ | 格式化输出，默认 `true` |

---

### 🌐 Web Enhanced 工具包

基于 Playwright + AIOHTTP 的高级网页抓取工具。

#### `web_fetch_js`

用 Playwright 渲染 JavaScript 后抓取页面内容。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 目标 URL |
| `selector` | string | ❌ | CSS 选择器，仅提取匹配元素 |
| `wait_for` | string | ❌ | 等待选择器出现后再抓取 |
| `timeout` | int | ❌ | 超时秒数，默认 30 |
| `use_cookies` | string | ❌ | Cookie 文件路径（由 web_login 生成） |

#### `web_batch_fetch`

批量并发抓取多个 URL。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `urls` | string | ✅ | URL 列表，JSON 数组格式 |
| `max_concurrent` | int | ❌ | 最大并发数，默认 5 |
| `timeout` | int | ❌ | 每个请求超时秒数，默认 30 |

#### `web_search_enhanced`

增强搜索（支持时间/站点过滤、结果提取）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词 |
| `max_results` | int | ❌ | 最大结果数，默认 10 |
| `time_range` | string | ❌ | 时间范围：`day` / `week` / `month` / `year` |
| `site` | string | ❌ | 限制站点，如 `github.com` |
| `fetch_content` | bool | ❌ | 是否抓取结果页面内容，默认 `false` |

#### `web_login`

浏览器登录并保存 Cookies。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 登录页面 URL |
| `username_selector` | string | ✅ | 用户名输入框 CSS 选择器 |
| `password_selector` | string | ✅ | 密码输入框 CSS 选择器 |
| `username` | string | ✅ | 用户名 |
| `password` | string | ✅ | 密码 |
| `submit_selector` | string | ❌ | 提交按钮选择器（为空则按 Enter） |
| `cookies_file` | string | ❌ | Cookie 保存路径 |
| `wait_after_login` | int | ❌ | 登录后等待秒数，默认 3 |
| `verify_selector` | string | ❌ | 登录成功后验证元素选择器 |

---

## 配置

复制配置模板并修改：

```bash
cp config/defaults.example.json config/defaults.json
```

`config/defaults.json`：

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

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `model` | Droid 使用的模型 | — |
| `auto_level` | 自动执行级别 `low` / `medium` / `high` | `high` |
| `reasoning_effort` | 推理强度 `none` / `low` / `medium` / `high` | `none` |
| `interaction_mode` | 交互模式 | `auto` |
| `cwd` | 代理工作目录 | 项目 workspace 目录 |
| `poll_interval_seconds` | 轮询间隔 | `30` |
| `max_wait_minutes` | 最大等待时间 | `15` |

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DROID_BIN` | Droid CLI 路径 | `droid` |

## 开发

### 添加新工具包

1. 在 `mcp-server/toolkits/` 下创建新文件，继承 `BaseToolkit`：

```python
from .base import BaseToolkit

class MyToolkit(BaseToolkit):
    name = "my_toolkit"
    description = "我的工具包"

    def get_config_schema(self) -> dict:
        return {"key": "说明"}

    def get_tools(self) -> list:
        return [
            (self.my_tool, "my_tool", "工具描述"),
        ]

    async def my_tool(self, param: str) -> dict:
        return {"result": "..."}
```

2. 在 `toolkits/__init__.py` 中导出
3. 在 `toolkits/manager.py` 中注册
4. 在 `server.py` 中添加工具路由（使用 `@_reg` 装饰器）

## License

MIT
