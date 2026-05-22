"""
奇门遁甲 — 长生十二神
"""

from . import tables as T
from . import ganzhi


def _new_list(lst, start):
    idx = lst.index(start)
    return lst[idx:] + lst[:idx]


def twelve_stages(year, month, day, hour, minute, option):
    """
    时家长生十二神
    返回 {"天盤": {...}, "地盤": {...}}
    """
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    return _compute_stages(gz[2][0], option, year, month, day, hour, minute)


def twelve_stages_minute(year, month, day, hour, minute, option):
    """
    刻家长生十二神
    """
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    return _compute_stages_minute(gz[3][0], option, year, month, day, hour, minute)


def _find_shier_luck(gan):
    """天干 → 十二长生映射 {地支: 长生阶段}"""
    # 阳干
    cs = ["長生", "沐浴", "冠帶", "臨冠", "帝旺"]

    # 阳干起始地支
    yang_starts = {
        "甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
    }
    # 阴干起始地支
    yin_starts = {
        "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯",
    }

    di_zhi = list(T.DI_ZHI)

    if gan in yang_starts:
        start = yang_starts[gan]
        nlist = _new_list(di_zhi, start)
        cslist = dict(zip(nlist, cs + list("衰病死墓絕胎養")))
        return cslist
    elif gan in yin_starts:
        start = yin_starts[gan]
        nlist = _new_list(di_zhi, start)
        cheungsunlist = list("死病衰") + ["帝旺", "臨冠", "冠帶", "沐浴", "長生"] + list("養胎絕墓")
        return dict(zip(nlist, cheungsunlist))
    return {}


def _compute_stages(day_gan, option, year, month, day, hour, minute):
    """时家长生运"""
    from . import plates

    sky = plates.sky_plate(year, month, day, hour, minute, option)
    earth = plates.earth_plate(
        {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
            year, month, day, hour, minute))

    find_twelve_luck = _find_shier_luck(day_gan)

    # 地支→天干映射 (用于将长生映射到天干)
    zhi_gan_map = T.ZHI_TO_GAN
    luck_by_gan = {zhi_gan_map.get(k): v for k, v in find_twelve_luck.items()}

    # 天盘
    try:
        sky_pan = sky[0] if isinstance(sky, tuple) else sky
        sky_new = {k: {v: luck_by_gan.get(k)} for k, v in sky_pan.items()}
    except (KeyError, TypeError):
        sky_pan = sky if isinstance(sky, dict) else sky
        c = [{i: luck_by_gan.get(i)} for i in sky_pan.values()]
        sky_new = dict(zip(list(sky_pan.keys()), c))

    # 地盘
    earth_new = {k: {v: luck_by_gan.get(v)} for k, v in earth.items()}

    return {"天盤": sky_new, "地盤": earth_new}


def _compute_stages_minute(hour_gan, option, year, month, day, hour, minute):
    """刻家长生运"""
    from . import plates

    sky = plates.sky_plate_minute(year, month, day, hour, minute, option)
    earth = plates.earth_plate(
        {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
            year, month, day, hour, minute))

    find_twelve_luck = _find_shier_luck(hour_gan)
    zhi_gan_map = T.ZHI_TO_GAN
    luck_by_gan = {zhi_gan_map.get(k): v for k, v in find_twelve_luck.items()}

    # 天盘
    try:
        sky_pan = sky[0] if isinstance(sky, tuple) else sky
        sky_new = {k: {v: luck_by_gan.get(k)} for k, v in sky_pan.items()}
    except (KeyError, TypeError):
        sky_pan = sky if isinstance(sky, dict) else sky
        b = [{i: luck_by_gan.get(i)} for i in sky_pan.values()]
        sky_new = dict(zip(list(sky_pan.keys()), b))

    # 地盘
    earth_new = {k: {v: luck_by_gan.get(v)} for k, v in earth.items()}

    return {"天盤": sky_new, "地盤": earth_new}
