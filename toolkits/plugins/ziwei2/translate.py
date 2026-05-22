"""
紫微斗数 — 中英文翻译层
"""

from . import tables as T


def hour_to_index(hour: int) -> int:
    """小时 → 时辰索引 (0-11)"""
    if hour == 23 or hour == 0:
        return 0
    for idx, (start, end) in enumerate(T.HOUR_RANGES):
        if start <= hour < end:
            return idx
    return 6  # 默认午时


def gan(key: str) -> str:
    """英文天干 key → 中文"""
    return T.GAN_MAP.get(key, key)


def zhi(key: str) -> str:
    """英文地支 key → 中文"""
    return T.ZHI_MAP.get(key, key)


def ganzhi(heavenly_key: str, earthly_key: str) -> str:
    """天干+地支 → 中文干支"""
    return gan(heavenly_key) + zhi(earthly_key)


def star_name(name: str) -> str:
    """英文星曜名 → 中文（含主星、辅星、杂曜）"""
    return T.STAR_NAME_MAP.get(name, T.ADJECTIVE_STAR_MAP.get(name, name))


def brightness(val) -> str:
    """英文亮度 → 中文"""
    if val is None:
        return ""
    return T.BRIGHTNESS_MAP.get(val, val or "")


def mutagen(val) -> str:
    """英文四化 → 中文"""
    if val is None:
        return ""
    return T.MUTAGEN_MAP.get(val, val)


def five_elements(key: str) -> str:
    """英文五行局 → 中文"""
    return T.FIVE_ELEMENTS_MAP.get(key, key)


def star_info(star_obj) -> dict:
    """星曜对象 → 标准化 dict"""
    return {
        "name": star_name(star_obj.name),
        "brightness": brightness(star_obj.brightness),
        "mutagen": mutagen(star_obj.mutagen),
    }


def star_names(star_list) -> list[str]:
    """星曜对象列表 → 中文名列表"""
    return [star_name(s.name) for s in star_list]


def star_display_list(star_list) -> list[str]:
    """星曜对象列表 → '星名(亮度)' 格式"""
    return [
        f"{star_name(s.name)}({brightness(s.brightness)})"
        for s in star_list if s.brightness
    ]


def mutagen_display_list(star_list) -> list[str]:
    """有四化的星曜 → '星名四化' 格式"""
    return [
        f"{star_name(s.name)}{mutagen(s.mutagen)}"
        for s in star_list if s.mutagen
    ]
