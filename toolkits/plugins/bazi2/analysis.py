"""
八字 — 分析功能（五行/大运/流年/流月）
"""

from datetime import datetime
from typing import Optional

from lunar_python import Solar

from . import translate as Tr
from . import tables as T
from . import chart as chart_mod


def wuxing_stats(birth_date: str, birth_time: str) -> dict:
    """五行分析"""
    eight_char, lunar, meta = chart_mod.create(birth_date, birth_time)

    elements = {e: 0 for e in T.WUXING_ALL}
    gan_list = []
    zhi_list = []

    for key in T.PILLAR_KEYS:
        gan = getattr(eight_char, f"get{key}Gan")()
        zhi = getattr(eight_char, f"get{key}Zhi")()
        gan_list.append(gan)
        zhi_list.append(zhi)

        elements[Tr.element_cn(gan)] += 1
        elements[Tr.element_cn(zhi)] += 1

        hide = getattr(eight_char, f"get{key}HideGan")()
        for hg in hide:
            elem = Tr.element_cn(hg)
            if elem:
                elements[elem] += 0.5

    dm = chart_mod.day_master(eight_char)
    day_elem = dm["element"]
    total = sum(elements.values())

    distribution = {
        k: {"count": v, "percent": round(v / total * 100, 1)}
        for k, v in elements.items()
    }

    missing = [k for k, v in elements.items() if v == 0]
    weak = [k for k, v in elements.items() if 0 < v < total * 0.1]
    strong = [k for k, v in elements.items() if v > total * 0.35]

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "day_master": dm["gan"],
        "day_master_element": day_elem,
        "bazi_ganzhi": " ".join(gan_list[i] + zhi_list[i] for i in range(4)),
        "element_distribution": distribution,
        "missing": missing,
        "weak": weak,
        "strong": strong,
        "sheng_element": T.SHENG_MAP.get(day_elem, ""),
        "ke_element": T.KE_MAP.get(day_elem, ""),
        "analysis_hint": (
            f"日主{dm['gan']}属{day_elem}，"
            + (f"五行缺{'、'.join(missing)}，" if missing else "五行俱全，")
            + (f"旺于{'、'.join(strong)}，" if strong else "")
            + f"生{day_elem}者为{T.BEI_KE_MAP.get(day_elem, '')}，"
            + f"泄{day_elem}者为{T.SHENG_MAP.get(day_elem, '')}"
        ),
    }


def dayun_list(birth_date: str, birth_time: str, gender: str = "男",
               limit: int = 8) -> dict:
    """大运排列"""
    eight_char, lunar, meta = chart_mod.create(birth_date, birth_time)
    y = meta["year"]
    gender_num = 1 if gender in ("男", "male", "M", "m", "1") else 0

    yun = eight_char.getYun(gender_num)
    start_age = yun.getStartYear()
    start_month = yun.getStartMonth()
    start_day = yun.getStartDay()

    result = []
    for dy in yun.getDaYun()[1:limit + 1]:
        gz = dy.getGanZhi()
        if not gz:
            continue
        liunian = []
        for ln in dy.getLiuNian():
            liunian.append({
                "year": ln.getYear(),
                "ganzhi": ln.getGanZhi(),
                "age": ln.getYear() - y,
            })
        result.append({
            "ganzhi": gz,
            "start_age": dy.getStartAge(),
            "start_year": dy.getStartYear(),
            "element": Tr.element_cn(gz[0]),
            "liunian": liunian,
        })

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "gender": gender,
        "start_age": start_age,
        "start_age_detail": f"{start_age}岁{start_month}个月{start_day}天",
        "direction": "顺行" if gender_num == 1 else "逆行",
        "dayun": result,
    }


def liunian_analysis(birth_date: str, birth_time: str, gender: str = "男",
                     target_year: Optional[int] = None) -> dict:
    """流年分析"""
    eight_char, lunar, meta = chart_mod.create(birth_date, birth_time)
    y = meta["year"]

    if target_year is None:
        target_year = datetime.now().year
    target_year = int(target_year)
    age = target_year - y

    gender_num = 1 if gender in ("男", "male", "M", "m", "1") else 0
    yun = eight_char.getYun(gender_num)

    # 定位当前大运
    current_dy_gz = ""
    for dy in yun.getDaYun()[1:]:
        if dy.getStartAge() <= age:
            current_dy_gz = dy.getGanZhi()

    # 流年干支
    solar_ly = Solar.fromYmd(target_year, 1, 1)
    lunar_ly = solar_ly.getLunar()
    ly_ganzhi = lunar_ly.getYearInGanZhi()
    ly_gan = ly_ganzhi[0]
    ly_zhi = ly_ganzhi[1]
    ly_elem = Tr.element_cn(ly_gan)

    dm = chart_mod.day_master(eight_char)
    day_elem = dm["element"]
    relation = Tr.wuxing_relation(day_elem, ly_elem)

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "target_year": target_year,
        "age": age,
        "year_ganzhi": ly_ganzhi,
        "year_gan": ly_gan,
        "year_zhi": ly_zhi,
        "year_element": ly_elem,
        "year_zhi_element": Tr.element_cn(ly_zhi),
        "current_dayun": current_dy_gz,
        "relation_to_day_master": relation,
        "day_master": dm["gan"],
        "day_master_element": day_elem,
        "analysis_hint": (
            f"{target_year}年{ly_ganzhi}，天干{ly_gan}属{ly_elem}，"
            f"与日主{dm['gan']}({day_elem})的关系：{relation}"
        ),
    }


def liuyue_analysis(birth_date: str, birth_time: str, gender: str = "男",
                    target_year: int = None, target_month: int = None) -> dict:
    """流月分析（新增功能）"""
    eight_char, lunar, meta = chart_mod.create(birth_date, birth_time)
    y = meta["year"]

    if target_year is None or target_month is None:
        return {"error": "流月分析需要指定 target_year 和 target_month 参数"}

    target_year = int(target_year)
    target_month = int(target_month)
    age = target_year - y

    # 流月干支 — 用 lunar_python 取该月的月柱
    solar_m = Solar.fromYmd(target_year, target_month, 15)
    lunar_m = solar_m.getLunar()
    eight_m = lunar_m.getEightChar()
    month_gz = eight_m.getMonth()
    month_gan = eight_m.getMonthGan()
    month_zhi = eight_m.getMonthZhi()

    month_elem = Tr.element_cn(month_gan)
    month_zhi_elem = Tr.element_cn(month_zhi)

    # 日主
    dm = chart_mod.day_master(eight_char)
    day_elem = dm["element"]
    relation = Tr.wuxing_relation(day_elem, month_elem)

    # 当前大运
    gender_num = 1 if gender in ("男", "male", "M", "m", "1") else 0
    yun = eight_char.getYun(gender_num)
    current_dy_gz = ""
    for dy in yun.getDaYun()[1:]:
        if dy.getStartAge() <= age:
            current_dy_gz = dy.getGanZhi()

    # 流年干支
    solar_ly = Solar.fromYmd(target_year, 1, 1)
    lunar_ly = solar_ly.getLunar()
    ly_ganzhi = lunar_ly.getYearInGanZhi()

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "target_year": target_year,
        "target_month": target_month,
        "age": age,
        "month_ganzhi": month_gz,
        "month_gan": month_gan,
        "month_zhi": month_zhi,
        "month_element": month_elem,
        "month_zhi_element": month_zhi_elem,
        "year_ganzhi": ly_ganzhi,
        "current_dayun": current_dy_gz,
        "relation_to_day_master": relation,
        "day_master": dm["gan"],
        "day_master_element": day_elem,
        "analysis_hint": (
            f"{target_year}年{target_month}月 流月{month_gz}，"
            f"天干{month_gan}属{month_elem}，"
            f"与日主{dm['gan']}({day_elem})的关系：{relation}"
        ),
    }
