"""
ziwei2 — 紫微斗数重构版

库模块: ziwei.py, chart.py, analysis.py, tables.py, translate.py
工具包入口: Ziwei2Toolkit
"""

from typing import Optional

from toolkits.base import BaseToolkit
from .ziwei import Ziwei

__all__ = ["Ziwei", "Ziwei2Toolkit"]


class Ziwei2Toolkit(BaseToolkit):
    """Ziwei2 紫微斗数工具包（重构版）"""

    name = "ziwei2"
    description = "紫微斗数工具包(重构版) - 排盘/宫位分析/大限/流年/流月"

    def __init__(self, ctx: dict = None):
        super().__init__()

    def get_config_schema(self) -> dict:
        return {}

    def get_tools(self):
        return [
            (self.ziwei2_chart, "ziwei2_chart",
             "紫微排盘（命宫身宫/十四主星/四化/亮度/五行局）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女")]),
            (self.ziwei2_palace, "ziwei2_palace",
             "宫位分析（星曜组合与三方四正）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女"),
              ("palace_name", "str", "命宫", "宫位名称")]),
            (self.ziwei2_daxian, "ziwei2_daxian",
             "大限排列（各步大限宫位和星曜）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女")]),
            (self.ziwei2_liunian, "ziwei2_liunian",
             "流年分析（当年命宫/四化/大限）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女"),
              ("year", "Optional[int]", None, "目标年份，默认今年")]),
            (self.ziwei2_liuyue, "ziwei2_liuyue",
             "流月分析（指定年月的流月命宫/四化）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女"),
              ("year", "Optional[int]", None, "目标年份"),
              ("month", "Optional[int]", None, "目标月份（1-12）")]),
        ]

    def _get_zw(self, birth_date, birth_time, gender):
        return Ziwei(birth_date, birth_time, gender)

    async def ziwei2_chart(self, birth_date: str, birth_time: str,
                           gender: str = "男") -> dict:
        try:
            return self._get_zw(birth_date, birth_time, gender).chart()
        except Exception as e:
            return {"error": f"排盘失败: {e}"}

    async def ziwei2_palace(self, birth_date: str, birth_time: str,
                            gender: str = "男", palace_name: str = "命宫") -> dict:
        try:
            return self._get_zw(birth_date, birth_time, gender).palace(palace_name)
        except Exception as e:
            return {"error": f"宫位分析失败: {e}"}

    async def ziwei2_daxian(self, birth_date: str, birth_time: str,
                            gender: str = "男") -> dict:
        try:
            return self._get_zw(birth_date, birth_time, gender).daxian()
        except Exception as e:
            return {"error": f"大限排列失败: {e}"}

    async def ziwei2_liunian(self, birth_date: str, birth_time: str,
                             gender: str = "男", year: Optional[int] = None) -> dict:
        try:
            return self._get_zw(birth_date, birth_time, gender).liunian(year)
        except Exception as e:
            return {"error": f"流年分析失败: {e}"}

    async def ziwei2_liuyue(self, birth_date: str, birth_time: str,
                            gender: str = "男", year: int = None,
                            month: int = None) -> dict:
        try:
            if year is None or month is None:
                return {"error": "流月分析需要指定 year 和 month 参数"}
            return self._get_zw(birth_date, birth_time, gender).liuyue(year, month)
        except Exception as e:
            return {"error": f"流月分析失败: {e}"}
