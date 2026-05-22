"""
紫微斗数 — 分析功能（宫位/三方四正/大限/流年/流月）
"""

from datetime import datetime
from typing import Optional

from . import translate as Tr
from . import tables as T
from . import chart as chart_mod

# 英文宫名 → 中文
PALACE_EN_ZH = {
    'soulPalace': '命宫', 'siblingsPalace': '兄弟宫', 'spousePalace': '夫妻宫',
    'childrenPalace': '子女宫', 'wealthPalace': '财帛宫', 'healthPalace': '疾厄宫',
    'surfacePalace': '迁移宫', 'friendsPalace': '交友宫', 'careerPalace': '官禄宫',
    'propertyPalace': '田宅宫', 'spiritPalace': '福德宫', 'parentsPalace': '父母宫',
}


def _horoscope_palaces(horo_item, natal_palaces: list) -> list[dict]:
    """
    从 horoscope item (yearly/monthly/age/decadal) 构建流盘十二宫布局。
    horoscope 的 palace_names 是按原盘 index 重排后的宫名列表，
    表示流年/流月的命宫落在原盘的第几个宫位。
    """
    result = []
    palace_names = getattr(horo_item, 'palace_names', []) or []
    for i, pn_en in enumerate(palace_names):
        natal = natal_palaces[i] if i < len(natal_palaces) else {}
        result.append({
            "position": i,
            "name": PALACE_EN_ZH.get(pn_en, pn_en),
            "natal_palace": natal.get("name", ""),
            "natal_ganzhi": natal.get("ganzhi", ""),
            "major_stars": natal.get("major_stars", []),
            "is_soul": i == horo_item.index,
        })
    return result


def _horoscope_summary(horo_item, natal_palaces: list) -> dict:
    """构建流盘摘要：命宫位置 + 十二宫布局 + 四化"""
    gz = Tr.ganzhi(horo_item.heavenly_stem, horo_item.earthly_branch)
    mutagen_stars = [Tr.star_name(s) for s in (horo_item.mutagen or [])]
    palaces = _horoscope_palaces(horo_item, natal_palaces)

    # 命宫所在原盘宫位
    soul_idx = horo_item.index
    soul_palace = palaces[soul_idx] if soul_idx < len(palaces) else {}

    return {
        "ganzhi": gz,
        "mutagen_stars": mutagen_stars,
        "soul_palace_index": soul_idx,
        "soul_in_natal": soul_palace.get("natal_palace", ""),
        "palaces": palaces,
    }


def palace_analysis(birth_date: str, birth_time: str, gender: str,
                    palace_name: str = "命宫") -> dict:
    """单宫详情 + 三方四正"""
    ch, meta = chart_mod.create(birth_date, birth_time, gender)

    target = None
    for p in ch.palaces:
        pn = p.translate_name()
        if pn == palace_name or palace_name in pn:
            target = p
            break

    if target is None:
        return {"error": f"未知宫位: {palace_name}. 可用: {', '.join(T.PALACE_NAMES)}"}

    # 三方四正
    sanfang = []
    surrounded = ch.surrounded_palaces(target.index)
    if surrounded:
        for sp in surrounded.all_palaces():
            sanfang.append({
                "name": sp.translate_name(),
                "ganzhi": Tr.ganzhi(sp.heavenly_stem, sp.earthly_branch),
                "major_stars": Tr.star_names(sp.major_stars),
            })

    detail = chart_mod.palace_detail(target)
    detail["palace_name"] = detail["name"]  # 兼容原版字段名
    detail["sanfang_sizheng"] = sanfang
    detail["birth_date"] = birth_date
    detail["birth_time"] = birth_time
    return detail


def daxian_list(birth_date: str, birth_time: str, gender: str) -> dict:
    """大限排列"""
    ch, meta = chart_mod.create(birth_date, birth_time, gender)

    result = []
    for p in ch.palaces:
        d = p.decadal
        if d and d.range:
            start_age, end_age = d.range
            gz = Tr.ganzhi(d.heavenly_stem, d.earthly_branch)
            result.append({
                "range": f"{start_age}-{end_age}岁",
                "start_age": start_age,
                "end_age": end_age,
                "ganzhi": gz,
                "palace": p.translate_name(),
                "major_stars_in_palace": Tr.star_names(p.major_stars),
            })

    result.sort(key=lambda x: x["start_age"])
    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "gender": meta["gender"],
        "daxian": result,
    }


def get_current_daxian(ch, age) -> dict:
    """定位当前大限"""
    for p in ch.palaces:
        d = p.decadal
        if d and d.range:
            start_age, end_age = d.range
            if start_age <= age <= end_age:
                return {
                    "range": f"{start_age}-{end_age}岁",
                    "ganzhi": Tr.ganzhi(d.heavenly_stem, d.earthly_branch),
                    "palace": p.translate_name(),
                }
    return {}


def liunian_analysis(birth_date: str, birth_time: str, gender: str,
                     target_year: Optional[int] = None) -> dict:
    """流年分析"""
    ch, meta = chart_mod.create(birth_date, birth_time, gender)
    y, m, d = meta["year"], meta["month"], meta["day"]
    time_idx = Tr.hour_to_index(meta["hour"])

    if target_year is None:
        target_year = datetime.now().year
    target_year = int(target_year)
    age = target_year - y

    horo = ch.horoscope(f"{target_year}-{m}-{d}", time_idx)

    # 原盘十二宫标准化数据（用于流年宫位映射）
    natal = chart_mod.all_palaces(ch)

    # 流年
    yearly = _horoscope_summary(horo.yearly, natal)

    # 小限
    xiaoxian = _horoscope_summary(horo.age, natal)

    # 大限
    decadal_summary = _horoscope_summary(horo.decadal, natal)

    current_dx = get_current_daxian(ch, age)

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "target_year": target_year,
        "age": age,
        "nominal_age": horo.nominal_age,
        "yearly": yearly,
        "xiaoxian": xiaoxian,
        "decadal": decadal_summary,
        "current_daxian": current_dx,
        "analysis_hint": (
            f"{target_year}年 流年{yearly['ganzhi']}（命宫在原盘{yearly['soul_in_natal']}），"
            f"小限{xiaoxian['ganzhi']}（命宫在原盘{xiaoxian['soul_in_natal']}），"
            + (f"大限{current_dx['ganzhi']}（{current_dx['palace']}），" if current_dx else "")
            + f"流年四化：{'、'.join(yearly['mutagen_stars'])}"
        ),
    }


def liuyue_analysis(birth_date: str, birth_time: str, gender: str,
                    target_year: int, target_month: int) -> dict:
    """流月分析（新增功能）"""
    ch, meta = chart_mod.create(birth_date, birth_time, gender)
    y, m, d = meta["year"], meta["month"], meta["day"]
    time_idx = Tr.hour_to_index(meta["hour"])

    target_year = int(target_year)
    target_month = int(target_month)
    age = target_year - y

    horo = ch.horoscope(f"{target_year}-{target_month}-{d}", time_idx)

    # 原盘十二宫标准化数据
    natal = chart_mod.all_palaces(ch)

    # 流月
    monthly = _horoscope_summary(horo.monthly, natal)

    # 流年
    yearly = _horoscope_summary(horo.yearly, natal)

    # 大限
    decadal_s = _horoscope_summary(horo.decadal, natal)

    current_dx = get_current_daxian(ch, age)

    return {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "target_year": target_year,
        "target_month": target_month,
        "age": age,
        "monthly": monthly,
        "yearly": yearly,
        "decadal": decadal_s,
        "current_daxian": current_dx,
        "analysis_hint": (
            f"{target_year}年{target_month}月 流月{monthly['ganzhi']}（命宫在原盘{monthly['soul_in_natal']}），"
            f"流年{yearly['ganzhi']}（命宫在原盘{yearly['soul_in_natal']}），"
            + (f"大限{current_dx['ganzhi']}（{current_dx['palace']}），" if current_dx else "")
            + f"流月四化：{'、'.join(monthly['mutagen_stars'])}"
        ),
    }
