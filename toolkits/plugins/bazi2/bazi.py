"""
八字 — Bazi 主类 Pipeline 编排
"""

from typing import Optional

from . import chart
from . import analysis


class Bazi:
    """四柱八字排盘"""

    def __init__(self, birth_date: str, birth_time: str, gender: str = "男"):
        self.birth_date = birth_date
        self.birth_time = birth_time
        self.gender = gender

    def chart(self) -> dict:
        """排盘：四柱八字、藏干、十神、纳音、日主、命宫"""
        return chart.full_chart(self.birth_date, self.birth_time, self.gender)

    def wuxing(self) -> dict:
        """五行分析：统计五行分布，判断旺衰和缺失"""
        return analysis.wuxing_stats(self.birth_date, self.birth_time)

    def dayun(self, limit: int = 8) -> dict:
        """大运：起运年龄、大运排列、每步大运的流年"""
        return analysis.dayun_list(
            self.birth_date, self.birth_time, self.gender, limit)

    def liunian(self, year: Optional[int] = None) -> dict:
        """流年分析：当年天干地支与命盘关系"""
        return analysis.liunian_analysis(
            self.birth_date, self.birth_time, self.gender, year)

    def liuyue(self, year: int, month: int) -> dict:
        """流月分析：指定年月的流月干支与日主关系"""
        return analysis.liuyue_analysis(
            self.birth_date, self.birth_time, self.gender, year, month)
