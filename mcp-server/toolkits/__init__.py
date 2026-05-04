"""
工具包模块

可用工具包：
- droid: Factory Droid（文件管道模式）
- opencode: Opencode（HTTP API 模式）
- data_analysis: 数据分析工具包（CSV/JSON）
- web_enhanced: Web增强工具包（JS渲染抓取/搜索）
"""

from .base import BaseToolkit
from .droid import DroidToolkit
from .opencode import OpencodeToolkit
from .data_analysis import DataAnalysisToolkit
from .web_enhanced import WebEnhancedToolkit
from .manager import ToolkitManager

__all__ = [
    "BaseToolkit",
    "DroidToolkit",
    "OpencodeToolkit",
    "DataAnalysisToolkit",
    "WebEnhancedToolkit",
    "ToolkitManager",
]
