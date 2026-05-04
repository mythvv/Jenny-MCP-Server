# 贡献指南

感谢你对 Jenny MCP Server 的关注！欢迎提交 Issue 和 Pull Request。

## 快速开始

```bash
# 1. Fork 并克隆
git clone https://github.com/your-username/jenny-mcp-server.git
cd jenny-mcp-server

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 3. 安装开发依赖
pip install -e ".[dev,all]"

# 4. 安装 Playwright 浏览器（如需 web-enhanced）
playwright install chromium

# 5. 配置
cp config/defaults.example.json config/defaults.json
# 编辑 defaults.json

# 6. 启动测试
python mcp-server/server.py
```

## 开发流程

### 分支管理

- `main` — 稳定发布分支
- `dev` — 开发集成分支
- 功能分支：`feat/your-feature`
- 修复分支：`fix/your-fix`

### 提交信息

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat: 添加 xxx 工具包
fix: 修复会话超时不生效的问题
docs: 更新 API 文档
refactor: 重构工具注册机制
test: 添加 droid 工具包单元测试
chore: 更新依赖版本
```

### 代码规范

- 使用 `ruff` 进行 lint：`ruff check .`
- 使用 `ruff format` 格式化代码
- 类型注解：公共 API 必须添加类型注解
- 文档字符串：所有工具函数必须包含 docstring

### 测试

```bash
# 运行全部测试
pytest

# 运行特定模块
pytest tests/test_droid.py

# 带覆盖率
pytest --cov=mcp_server
```

## 添加新工具包

详见 README 中的「开发 → 添加新工具包」章节。简要步骤：

1. 在 `mcp-server/toolkits/` 下创建文件，继承 `BaseToolkit`
2. 实现 `get_tools()` 返回工具列表
3. 在 `__init__.py` 导出、`manager.py` 注册
4. 在 `server.py` 添加路由（`@_reg` 装饰器）
5. 更新 README API 文档
6. 添加测试

## Pull Request 流程

1. 确保通过所有测试：`pytest`
2. 确保代码规范：`ruff check .`
3. 更新相关文档（README、CHANGELOG）
4. 提交 PR，描述改动内容和动机
5. 等待 review

## Issue 报告

提交 Issue 时请包含：

- **环境信息**：Python 版本、OS、相关工具版本
- **复现步骤**：最小可复现的步骤
- **预期行为** vs **实际行为**
- **日志**：相关错误日志（注意移除敏感信息）

## 许可证

提交代码即表示你同意以 MIT 许可证发布你的贡献。
