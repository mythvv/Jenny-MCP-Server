"""
八字 — 排盘核心

调用 lunar_python，输出标准化结构。
"""

from lunar_python import Solar

from . import translate as Tr
from . import tables as T


def create(birth_date: str, birth_time: str):
    """
    创建八字命盘

    birth_date: "YYYY-MM-DD"
    birth_time: "HH:MM"
    返回: (eight_char, lunar, meta)
    """
    parts = birth_date.split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    tp = birth_time.split(":")
    h, mi = int(tp[0]), int(tp[1]) if len(tp) > 1 else 0

    solar = Solar.fromYmdHms(y, m, d, h, mi, 0)
    lunar = solar.getLunar()
    eight_char = lunar.getEightChar()

    meta = {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "year": y, "month": m, "day": d, "hour": h, "minute": mi,
    }
    return eight_char, lunar, meta


def four_pillars(eight_char) -> list[dict]:
    """四柱标准化输出"""
    result = []
    for key, name in zip(T.PILLAR_KEYS, T.PILLAR_NAMES):
        gan = getattr(eight_char, f"get{key}Gan")()
        zhi = getattr(eight_char, f"get{key}Zhi")()
        hide_gan = getattr(eight_char, f"get{key}HideGan")()
        na_yin = getattr(eight_char, f"get{key}NaYin")()
        shi_shen_gan = getattr(eight_char, f"get{key}ShiShenGan")() if key != "Day" else "日主"
        shi_shen_zhi = getattr(eight_char, f"get{key}ShiShenZhi")()

        result.append({
            "position": name,
            "ganzhi": getattr(eight_char, f"get{key}")(),
            "tian_gan": gan,
            "di_zhi": zhi,
            "tian_gan_element": Tr.element_cn(gan),
            "di_zhi_element": Tr.element_cn(zhi),
            "yinyang": Tr.yinyang(gan),
            "hide_gan": hide_gan,
            "na_yin": na_yin,
            "shi_shen_gan": shi_shen_gan,
            "shi_shen_zhi": shi_shen_zhi if shi_shen_zhi else [],
        })
    return result


def day_master(eight_char) -> dict:
    """日主信息"""
    gan = eight_char.getDayGan()
    elem = Tr.element_cn(gan)
    return {
        "gan": gan,
        "element": elem,
        "yinyang": Tr.yinyang(gan),
    }


def special_stars(eight_char) -> dict:
    """胎元/命宫/身宫等"""
    return {
        "ming_gong": eight_char.getMingGong(),
        "ming_gong_na_yin": eight_char.getMingGongNaYin(),
        "shen_gong": eight_char.getShenGong(),
        "shen_gong_na_yin": eight_char.getShenGongNaYin(),
        "tai_yuan": eight_char.getTaiYuan(),
        "tai_yuan_na_yin": eight_char.getTaiYuanNaYin(),
        "tai_xi": eight_char.getTaiXi(),
        "tai_xi_na_yin": eight_char.getTaiXiNaYin(),
    }


def full_chart(birth_date: str, birth_time: str, gender: str = "男") -> dict:
    """完整排盘"""
    eight_char, lunar, meta = create(birth_date, birth_time)
    gender_str = "男" if gender in ("男", "male", "M", "m", "1") else "女"

    lunar_str = (
        f"农历 {lunar.getYearInChinese()}年"
        f"{lunar.getMonthInChinese()}月"
        f"{lunar.getDayInChinese()}"
    )

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "lunar_date": lunar_str,
        "gender": gender_str,
        "four_pillars": four_pillars(eight_char),
        "day_master": day_master(eight_char),
        **special_stars(eight_char),
    }
