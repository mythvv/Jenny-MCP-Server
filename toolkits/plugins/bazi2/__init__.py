"""
bazi2 — 八字重构版

库模块: bazi.py, chart.py, analysis.py, tables.py, translate.py
工具包入口: Bazi2Toolkit
"""

from toolkits.base import BaseToolkit
from .bazi import Bazi

__all__ = ["Bazi", "Bazi2Toolkit"]


class Bazi2Toolkit(BaseToolkit):
    """Bazi2 四柱八字工具包（重构版）"""

    name = "bazi2"
    description = "四柱八字工具包(重构版) - 排盘/五行分析/大运/流年/流月"

    def __init__(self, ctx: dict = None):
        super().__init__()

    def get_config_schema(self) -> dict:
        return {}

    def get_tools(self):
        return [
            (self.bazi2_chart, "bazi2_chart",
             "八字排盘（四柱/藏干/十神/纳音/日主/命宫）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女")]),
            (self.bazi2_wuxing, "bazi2_wuxing",
             "五行分析（分布/旺衰/缺补）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM")]),
            (self.bazi2_dayun, "bazi2_dayun",
             "大运排列（起运年龄/大运/流年）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女"),
              ("limit", "int", 8, "显示大运步数")]),
            (self.bazi2_liunian, "bazi2_liunian",
             "流年分析（当年干支与日主关系）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女"),
              ("year", "Optional[int]", None, "目标年份，默认今年")]),
            (self.bazi2_liuyue, "bazi2_liuyue",
             "流月分析（指定年月干支与日主关系）",
             [("birth_date", "str", None, "出生日期，格式 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间，格式 HH:MM"),
              ("gender", "str", "男", "性别：男/女"),
              ("year", "Optional[int]", None, "目标年份"),
              ("month", "Optional[int]", None, "目标月份（1-12）")]),
        ]

    def _get_bz(self, birth_date, birth_time, gender):
        return Bazi(birth_date, birth_time, gender)

    async def bazi2_chart(self, birth_date: str, birth_time: str,
                          gender: str = "男") -> dict:
        try:
            return self._get_bz(birth_date, birth_time, gender).chart()
        except Exception as e:
            return {"error": f"排盘失败: {e}"}

    async def bazi2_wuxing(self, birth_date: str, birth_time: str) -> dict:
        try:
            return self._get_bz(birth_date, birth_time, "男").wuxing()
        except Exception as e:
            return {"error": f"五行分析失败: {e}"}

    async def bazi2_dayun(self, birth_date: str, birth_time: str,
                          gender: str = "男", limit: int = 8) -> dict:
        try:
            return self._get_bz(birth_date, birth_time, gender).dayun(limit)
        except Exception as e:
            return {"error": f"大运排列失败: {e}"}

    async def bazi2_liunian(self, birth_date: str, birth_time: str,
                            gender: str = "男", year: int = None) -> dict:
        try:
            return self._get_bz(birth_date, birth_time, gender).liunian(year)
        except Exception as e:
            return {"error": f"流年分析失败: {e}"}

    async def bazi2_liuyue(self, birth_date: str, birth_time: str,
                           gender: str = "男", year: int = None,
                           month: int = None) -> dict:
        try:
            if year is None or month is None:
                return {"error": "流月分析需要指定 year 和 month 参数"}
            return self._get_bz(birth_date, birth_time, gender).liuyue(year, month)
        except Exception as e:
            return {"error": f"流月分析失败: {e}"}
