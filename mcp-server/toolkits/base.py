"""
工具包抽象基类
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional


# 工具定义：(函数, 名称, 描述)
ToolDef = tuple[Callable, str, str]


class BaseToolkit(ABC):
    """工具包抽象基类"""

    name: str = ""
    description: str = ""

    def get_tools(self) -> list[ToolDef]:
        """返回工具包提供的工具列表。每项为 (fn, name, description)。

        fn 必须是 async 函数，接受业务参数，返回 dict。
        server.py 会自动包装 JSON 序列化和 toolkit 查找。
        """
        return []

    def get_info(self) -> dict:
        """返回工具包信息"""
        return {
            "name": self.name,
            "description": self.description,
            "config_schema": self.get_config_schema(),
            "tools": [name for _, name, _ in self.get_tools()],
            "tools_schema": self.get_tools_schema(),
        }

    def get_tools_schema(self) -> list[dict]:
        """返回工具的 schema 列表"""
        return [
            {"name": name, "description": desc} for _, name, desc in self.get_tools()
        ]

    @abstractmethod
    def get_config_schema(self) -> dict:
        """返回配置参数说明"""
        pass
