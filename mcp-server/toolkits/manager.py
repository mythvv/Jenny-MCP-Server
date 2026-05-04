"""
工具包管理器

管理工具包的注册、切换和调用。
"""

import inspect
import json
from typing import Optional

from .base import BaseToolkit
from .droid import DroidToolkit
from .opencode import OpencodeToolkit
from .data_analysis import DataAnalysisToolkit
from .web_enhanced import WebEnhancedToolkit


class ToolkitManager:
    """工具包管理器"""

    def __init__(
        self, sessions_dir: str, workspace_dir: str, default_config: dict = None
    ):
        self._toolkits: dict[str, BaseToolkit] = {}
        self._current: str = "droid"
        self._default_config = default_config or {}

        # 注册工具包
        self.register(DroidToolkit(sessions_dir, workspace_dir, default_config))
        self.register(
            OpencodeToolkit(
                workspace_dir, default_config.get("model", "opencode/big-pickle")
            )
        )
        self.register(DataAnalysisToolkit(workspace_dir))
        self.register(WebEnhancedToolkit())

    def register(self, toolkit: BaseToolkit):
        self._toolkits[toolkit.name] = toolkit

    def list_toolkits(self) -> list[dict]:
        return [t.get_info() for t in self._toolkits.values()]

    def switch(self, name: str, config: dict) -> dict:
        if name not in self._toolkits:
            return {
                "error": f"Toolkit {name} not found",
                "available": list(self._toolkits.keys()),
            }

        old = self._current
        self._current = name
        toolkit = self._toolkits[name]

        result = {
            "status": "switched",
            "from": old,
            "to": name,
            "toolkit": toolkit.get_info(),
            "tools_schema": self.get_tool_schemas(name),
        }

        # 传递配置给工具包
        if config:
            result["config_applied"] = config
            # 更新工具包配置
            if name == "opencode" and "model" in config:
                toolkit.default_model = self._parse_model(config["model"])

        return result

    def current(self) -> dict:
        toolkit = self._toolkits[self._current]
        return {
            "current": self._current,
            "toolkit": toolkit.get_info(),
        }

    def get(self) -> BaseToolkit:
        return self._toolkits[self._current]

    def get_tools_schema(self) -> list[dict]:
        """返回工具包的工具 schema 列表"""
        return [
            {"name": name, "description": desc}
            for _, name, desc in self._toolkits[self._current].get_tools()
        ]

    def get_tool_schemas(self, name: str) -> list[dict]:
        """返回指定工具包的工具 schema 列表（包含完整参数信息）"""
        if name not in self._toolkits:
            return []
        toolkit = self._toolkits[name]
        schemas = []
        for fn, tool_name, description in toolkit.get_tools():
            param_schemas = []
            try:
                sig = inspect.signature(fn)
                for pname, param in sig.parameters.items():
                    if pname in ("self", "cls"):
                        continue
                    ptype = param.annotation
                    if ptype is inspect.Parameter.empty:
                        ptype_str = "str"
                    elif hasattr(ptype, "__origin__"):
                        ptype_str = str(ptype)
                    else:
                        ptype_str = (
                            str(ptype.__name__)
                            if hasattr(ptype, "__name__")
                            else str(ptype)
                        )
                    pdefault = (
                        param.default.default
                        if hasattr(param.default, "default")
                        else param.default
                    )
                    pdoc = param.default if isinstance(param.default, str) else ""
                    param_schemas.append(
                        {
                            "name": pname,
                            "type": ptype_str,
                            "default": pdefault,
                            "description": pdoc,
                        }
                    )
            except Exception:
                pass
            schemas.append(
                {
                    "name": tool_name,
                    "description": description,
                    "parameters": param_schemas,
                }
            )
        return schemas

    def _parse_model(self, model_str: str) -> dict:
        """解析模型字符串"""
        if model_str and "/" in model_str:
            parts = model_str.split("/")
            return {"providerID": parts[0], "modelID": parts[1]}
        return {"providerID": "opencode", "modelID": "big-pickle"}
