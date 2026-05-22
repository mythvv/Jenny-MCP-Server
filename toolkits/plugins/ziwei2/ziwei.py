"""
紫微斗数 — Ziwei 主类 Pipeline 编排
"""

from typing import Optional

from . import chart
from . import analysis


class Ziwei:
    """紫微斗数排盘"""

    def __init__(self, birth_date: str, birth_time: str, gender: str = "男"):
        self.birth_date = birth_date
        self.birth_time = birth_time
        self.gender = gender

    def chart(self) -> dict:
        """排盘：命宫身宫、十二宫主星辅星、四化、星曜亮度、五行局"""
        return chart.full_chart(self.birth_date, self.birth_time, self.gender)

    def palace(self, palace_name: str = "命宫") -> dict:
        """宫位分析：指定宫位的星曜组合与三方四正"""
        return analysis.palace_analysis(
            self.birth_date, self.birth_time, self.gender, palace_name)

    def daxian(self) -> dict:
        """大限排列：各步大限宫位和星曜"""
        return analysis.daxian_list(self.birth_date, self.birth_time, self.gender)

    def liunian(self, year: Optional[int] = None) -> dict:
        """流年分析：当年命宫、四化、与大限关系"""
        return analysis.liunian_analysis(
            self.birth_date, self.birth_time, self.gender, year)

    def liuyue(self, year: int, month: int) -> dict:
        """流月分析：指定年月的流月命宫、四化、与大限关系"""
        return analysis.liuyue_analysis(
            self.birth_date, self.birth_time, self.gender, year, month)
