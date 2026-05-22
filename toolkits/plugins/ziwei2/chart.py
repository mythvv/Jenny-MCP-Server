"""
紫微斗数 — 排盘核心

调用 iztro-py，输出标准化结构。
"""

from iztro_py import astro
from . import translate as Tr
from . import tables as T


def create(birth_date: str, birth_time: str, gender: str):
    """
    创建紫微斗数命盘

    birth_date: "YYYY-MM-DD"
    birth_time: "HH:MM"
    gender: "男"/"女"
    返回: (chart, meta)
    """
    parts = birth_date.split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    h = int(birth_time.split(":")[0])
    time_index = Tr.hour_to_index(h)
    gender_str = "男" if gender in ("男", "male", "M", "m", "1") else "女"

    chart = astro.by_solar(f"{y}-{m}-{d}", time_index, gender_str)

    meta = {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "gender": gender_str,
        "year": y, "month": m, "day": d, "hour": h,
    }
    return chart, meta


def soul_body(chart) -> dict:
    """命宫身宫信息"""
    soul = chart.get_soul_palace()
    body = chart.get_body_palace()
    return {
        "soul_palace": {
            "name": soul.translate_name(),
            "ganzhi": Tr.ganzhi(soul.heavenly_stem, soul.earthly_branch),
            "index": soul.index,
        },
        "body_palace": {
            "name": body.translate_name(),
            "ganzhi": Tr.ganzhi(body.heavenly_stem, body.earthly_branch),
            "index": body.index,
        },
    }


def palace_detail(p) -> dict:
    """单个宫位标准化输出"""
    majors = [Tr.star_info(s) for s in p.major_stars]
    minors = [Tr.star_info(s) for s in p.minor_stars]
    adj_names = [Tr.star_name(s.name) for s in p.adjective_stars]

    return {
        "name": p.translate_name(),
        "index": p.index,
        "ganzhi": Tr.ganzhi(p.heavenly_stem, p.earthly_branch),
        "is_body_palace": p.is_body_palace,
        "major_stars": majors,
        "minor_stars": minors,
        "adjective_stars": adj_names,
        "brightness_detail": Tr.star_display_list(p.major_stars),
        "mutagen_stars": Tr.mutagen_display_list(p.major_stars + p.minor_stars),
        "changsheng12": p.changsheng12,
        "is_empty": p.is_empty(),
    }


def all_palaces(chart) -> list[dict]:
    """十二宫标准化输出"""
    return [palace_detail(p) for p in chart.palaces]


def five_elements(chart) -> str:
    """五行局"""
    return Tr.five_elements(chart.five_elements_class)


def full_chart(birth_date: str, birth_time: str, gender: str) -> dict:
    """完整排盘"""
    chart, meta = create(birth_date, birth_time, gender)

    return {
        "birth_date": meta["birth_date"],
        "birth_time": meta["birth_time"],
        "gender": meta["gender"],
        "solar_date": chart.solar_date,
        "lunar_date": chart.lunar_date,
        "chinese_date": chart.chinese_date,
        "zodiac": chart.zodiac,
        "five_elements_class": five_elements(chart),
        **soul_body(chart),
        "palaces": all_palaces(chart),
    }
