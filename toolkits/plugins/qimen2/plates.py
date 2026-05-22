"""
奇门遁甲 — 排盘核心 (地盘/天盘/八门/九星/八神)

统一旋转算法，无分支遗漏。
"""

import re
from itertools import cycle
from . import tables as T
from . import ganzhi


# ── 通用工具 ──

def _new_list(lst, start):
    idx = lst.index(start)
    return lst[idx:] + lst[:idx]


def _new_list_r(lst, start):
    idx = lst.index(start)
    result = []
    for i in range(len(lst)):
        result.append(lst[idx % len(lst)])
        idx -= 1
    return result


def _multi_get(d, key):
    for keys, v in d.items():
        if key in keys:
            return v
    return None


# ── 地盘 ──

def earth_plate(ju_str):
    """
    局数 → 地盘
    ju_str: "陽遁一局上元" 或 "陰遁三局中元"
    返回: {宫名: 天干}
    """
    yinyang = ju_str[:2]  # "陽遁" or "陰遁"
    number = ju_str[2]    # "一"~"九"

    # 九宫按局数旋转
    rotated_nums = _new_list(T.CNUMBER, number)
    gua_seq = [dict(zip(T.CNUMBER, T.EIGHT_GUA))[n] for n in rotated_nums]

    gan_seq = T.YANG_EARTH_GAN if yinyang == "陽遁" else T.YIN_EARTH_GAN
    return dict(zip(gua_seq, gan_seq))


def earth_plate_reverse(earth):
    """地盘反转: {天干: 宫名}"""
    return {v: k for k, v in earth.items()}


# ── 值符值使 ──

def zhifu_pai(ju_str):
    """值符排: {旬首: 位置编号序列}"""
    yinyang = ju_str[0]  # "陽" or "陰"
    kook = ju_str[2]     # "一"~"九"
    pai = T.ZF_PAI_BASE.get(yinyang, {}).get(kook, "")

    cnum = T.CNUMBER
    if yinyang == "陽":
        vals = [n + pai for n in _new_list(cnum, kook)[:6]]
    else:
        vals = [n + pai for n in _new_list_r(cnum, kook)[:6]]
    return dict(zip(T.JIAZI[0::10], vals))


def zhishi_pai(ju_str):
    """值使排: {旬首: 位置编号序列}"""
    yinyang = ju_str[0]
    kook = ju_str[2]
    cnum = T.CNUMBER

    nk = _new_list(cnum, kook)
    nrk = _new_list_r(cnum, kook)

    if yinyang == "陽":
        long_list = "".join(nk) * 3
        vals = [i + long_list[long_list.index(i)+1:][0:11] for i in nk[:6]]
    else:
        long_list = "".join(nrk) * 3
        vals = [i + long_list[long_list.index(i)+1:][0:11] for i in nrk[:6]]

    return dict(zip(T.JIAZI[0::10], vals))


def zhifu_n_zhishi(year, month, day, hour, minute, option):
    """
    找值符和值使 (时家)
    option: 1=拆补, 2=置闰
    """
    gongs_code = dict(zip(T.CNUMBER, T.EIGHT_GUA))
    gz = ganzhi.gangzhi(year, month, day, hour, minute)

    hgan = dict(zip(T.TIAN_GAN, range(0, 10))).get(gz[3][0])
    chour = ganzhi.get_xun(gz[3])

    # 获取局数
    ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
        year, month, day, hour, minute)

    # 值使排和值符排
    zs_pai = zhishi_pai(ju_str)
    zf_pai = zhifu_pai(ju_str)

    zs_keys = list(zs_pai.keys())
    zs_vals = list(zs_pai.values())
    zf_keys = list(zf_pai.keys())
    zf_vals = list(zf_pai.values())

    # 门和星对应
    door_map = dict(zip(T.CNUMBER, T.DOOR_STAR_ORIGINAL))
    star_map = dict(zip(T.CNUMBER, T.STAR_9))

    a = [door_map.get(v[0]) for v in zs_vals]    # 门
    b = [star_map.get(v[0]) for v in zf_vals]     # 星
    c = [gongs_code.get(v[hgan]) for v in zf_vals]  # 值符宫
    d = [gongs_code.get(v[hgan]) for v in zs_vals]  # 值使宫

    door = dict(zip(zs_keys, a)).get(chour)
    if door == "中":
        door = "死"

    return {
        "值符天干": [chour, T.LIUJIA_DUN.get(chour)],
        "值符星宮": [dict(zip(zf_keys, b)).get(chour),
                     dict(zip(zf_keys, c)).get(chour)],
        "值使門宮": [door, dict(zip(zs_keys, d)).get(chour)],
    }


def zhifu_n_zhishi_ke(year, month, day, hour, minute, option):
    """找值符和值使 (刻家)"""
    gongs_code = dict(zip(T.CNUMBER, T.EIGHT_GUA))
    gz = ganzhi.gangzhi(year, month, day, hour, minute)

    hgan = dict(zip(T.TIAN_GAN, range(0, 10))).get(gz[4][0])
    chour = ganzhi.get_xun(gz[4])

    # 刻家用时家局数做值符值使排
    ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
        year, month, day, hour, minute)

    ke_ju = ganzhi.ju_ke(year, month, day, hour, minute)

    # 值使排(刻家)
    zs_pai_ke = _zhishi_pai_ke(ju_str)
    zf_pai_ke = _zhifu_pai_ke(ju_str)

    zs_keys = list(zs_pai_ke.keys())
    zs_vals = list(zs_pai_ke.values())
    zf_keys = list(zf_pai_ke.keys())
    zf_vals = list(zf_pai_ke.values())

    door_map = dict(zip(T.CNUMBER, T.DOOR_STAR_ORIGINAL))
    star_map = dict(zip(T.CNUMBER, T.STAR_9))

    doorlist = [door_map.get(v[0]) for v in zs_vals]
    door = dict(zip(zs_keys, doorlist)).get(chour)
    if door == "中":
        door = "死"

    blist = [gongs_code.get(v[hgan]) for v in zf_vals]
    godlist = [star_map.get(v[0]) for v in zf_vals]
    zhifu_star = [dict(zip(zf_keys, godlist)).get(chour),
                  dict(zip(zf_keys, blist)).get(chour)]

    sdoor = [gongs_code.get(v[hgan]) for v in zf_vals]
    zhifu_door = [door, dict(zip(zf_keys, sdoor)).get(chour)]

    return {"值符星宮": zhifu_star, "值使門宮": zhifu_door}


def _zhifu_pai_ke(ju_str):
    """刻家值符排 (与 zhifu_pai 相同结构)"""
    return zhifu_pai(ju_str)


def _zhishi_pai_ke(ju_str):
    """刻家值使排 (与 zhishi_pai 相同结构)"""
    return zhishi_pai(ju_str)


# ── 天盘 ──

def sky_plate(year, month, day, hour, minute, option):
    """
    天盘 (时家)
    返回 dict 或 tuple(dict, dict) — 与原版保持一致
    """
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
        year, month, day, hour, minute)
    yinyang = ju_str[0]  # "陽" or "陰"

    earth = earth_plate(ju_str)
    earth_r = earth_plate_reverse(earth)
    rotate = T.CLOCKWISE_8 if yinyang == "陽" else list(reversed(T.CLOCKWISE_8))

    zfzs = zhifu_n_zhishi(year, month, day, hour, minute, option)
    fu_head = _hour_zhifu(year, month, day, hour, minute)[2]
    fu_location = earth_r.get(gz[3][0])
    fu_head_location = zfzs.get("值符星宮")[1]
    fu_head_location2 = earth_r.get(fu_head)
    zhifu = zfzs["值符星宮"][0]
    gan_head = zfzs.get("值符天干", [None, None])
    if isinstance(gan_head, list) and len(gan_head) > 1:
        gan_head = gan_head[1]

    gong_reorder_base = _new_list(rotate, "坤")

    # Case 1: 值符在 中宫
    if fu_head_location == "中":
        return _sky_at_center(earth, rotate, fu_head, gan_head, gong_reorder_base,
                              year, month, day, hour, minute, option)

    # Case 2: 值符不在中, 非禽星, 值符天干不在中
    if zhifu != "禽" and fu_head_location2 != "中":
        return _sky_normal(earth, rotate, fu_head, fu_head_location, fu_location,
                           ju_str)

    # Case 3: 禽星, 值符天干在中
    if zhifu == "禽" and fu_head_location2 == "中":
        return _sky_qin_at_center(earth, rotate, fu_head, fu_head_location,
                                  fu_location)

    # Case 4: 其他情况 — fallback 用地盘
    return earth


def _sky_at_center(earth, rotate, fu_head, gan_head, gong_reorder_base,
                   year, month, day, hour, minute, option):
    """天盘: 值符在中宫"""
    gong_reorder = gong_reorder_base
    a = [earth.get(g) for g in rotate]

    try:
        gan_reorder = _new_list(a, fu_head)
        return dict(zip(gong_reorder, gan_reorder))
    except ValueError:
        # fu_head 不在顺时针序列中
        earth_kun = earth.get("坤")
        if earth_kun:
            gan_reorder = _new_list(a, earth_kun)
            return dict(zip(gong_reorder, gan_reorder))
        return dict(zip(gong_reorder, a))


def _sky_normal(earth, rotate, fu_head, fu_head_location, fu_location, ju_str):
    """天盘: 正常旋转"""
    newlist = [earth.get(g) for g in rotate]

    try:
        gan_reorder = _new_list(newlist, fu_head)
    except ValueError:
        gan_reorder = newlist

    gong_reorder = _new_list(rotate, fu_head_location)

    if fu_head not in gan_reorder:
        start = dict(zip(T.CNUMBER, gan_reorder)).get(ju_str[2])
        if start:
            rgan_reorder = _new_list(gan_reorder, start)
            rgong_reorder = _new_list(gong_reorder, fu_location)
            return dict(zip(rgong_reorder, rgan_reorder)), dict(zip(rgan_reorder, rgong_reorder))
        return dict(zip(gong_reorder, gan_reorder))

    if fu_location is None:
        return earth

    return {**dict(zip(gong_reorder, gan_reorder)), **{"中": earth.get("中")}}


def _sky_qin_at_center(earth, rotate, fu_head, fu_head_location, fu_location):
    """天盘: 禽星+值符天干在中宫"""
    gg = [earth.get(g) for g in rotate]
    earth_kun = earth.get("坤")
    if not earth_kun:
        return earth

    try:
        gan_reorder = _new_list(gg, earth_kun)
    except ValueError:
        gan_reorder = gg

    gong_reorder = _new_list(rotate, fu_head_location)

    if fu_head not in gan_reorder:
        rgong_reorder = _new_list(gong_reorder, fu_location)
        return dict(zip(rgong_reorder, gan_reorder))

    return {**dict(zip(gong_reorder, gan_reorder)), **{"中": earth.get("中")}}


def sky_plate_minute(year, month, day, hour, minute, option):
    """
    天盘 (刻家)
    与 sky_plate 逻辑一致但用刻家局数和刻干支
    """
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    ke_ju = ganzhi.ju_ke(year, month, day, hour, minute)
    yinyang = ke_ju[0]

    earth_min = earth_plate_minute(year, month, day, hour, minute)
    earth_min_r = {v: k for k, v in earth_min.items()}
    rotate = T.CLOCKWISE_8 if yinyang == "陽" else list(reversed(T.CLOCKWISE_8))

    zfzs_ke = zhifu_n_zhishi_ke(year, month, day, hour, minute, option)
    fu_head = _hour_zhifu_minute(year, month, day, hour, minute)[2]
    fu_location = earth_min_r.get(gz[4][0])
    fu_head_location = zfzs_ke.get("值符星宮")[1]
    fu_head_location2 = earth_min_r.get(fu_head)
    zhifu = zfzs_ke["值符星宮"][0]

    if fu_head_location == "中":
        # 原版在中心分支用时家地盘 pan_earth(option)
        ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
            year, month, day, hour, minute)
        earth_shi = earth_plate(ju_str)
        gong_reorder = _new_list(rotate, "坤")
        try:
            g = [earth_shi.get(x) for x in rotate]
            gan_reorder = _new_list(g, fu_head)
            gong_reorder2 = _new_list(rotate, fu_head_location)
            return dict(zip(gong_reorder2, gan_reorder))
        except ValueError:
            # 与原版 pan_sky_minute 的 except 分支一致
            aaa = [earth_shi.get(x) for x in list(reversed(rotate))]
            earth_kun = earth_shi.get("坤")
            if earth_kun:
                aaa_bbb = _new_list(aaa, earth_kun)
                return dict(zip(list(reversed(gong_reorder)), aaa_bbb))
            return dict(zip(gong_reorder, aaa))

    if fu_head_location != "中" and zhifu != "禽" and fu_head_location2 != "中":
        rotate_list = [earth_min.get(x) for x in rotate]
        try:
            gan_reorder = _new_list(rotate_list, fu_head)
        except ValueError:
            gan_reorder = rotate_list

        gong_reorder = _new_list(rotate, fu_head_location)
        if fu_head not in gan_reorder:
            ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
                year, month, day, hour, minute)
            start = dict(zip(T.CNUMBER, gan_reorder)).get(ju_str[2])
            if start:
                rgan_reorder = _new_list(gan_reorder, start)
                rgong_reorder = _new_list(gong_reorder, fu_location)
                return dict(zip(rgong_reorder, rgan_reorder)), dict(zip(rgan_reorder, rgong_reorder))
            return dict(zip(gong_reorder, gan_reorder))

        if fu_location is None:
            return earth_min
        return {**dict(zip(gong_reorder, gan_reorder)), **{"中": earth_min.get("中")}}

    if fu_head_location != "中" and zhifu == "禽" and fu_head_location2 == "中":
        earth_rotate = [earth_min.get(x) for x in rotate]
        earth_kun = earth_min.get("坤")
        if earth_kun:
            try:
                gan_reorder = _new_list(earth_rotate, earth_kun)
            except ValueError:
                gan_reorder = earth_rotate
        else:
            gan_reorder = earth_rotate
        gong_reorder = _new_list(rotate, fu_head_location)
        if fu_head not in gan_reorder:
            rgong_reorder = _new_list(gong_reorder, fu_location)
            return dict(zip(rgong_reorder, gan_reorder))
        return {**dict(zip(gong_reorder, gan_reorder)), **{"中": earth_min.get("中")}}

    # Fallback: 与原版 patch 行为一致，退回到时家天盘
    return sky_plate(year, month, day, hour, minute, option)


def _hour_zhifu(year, month, day, hour, minute):
    """时干支值符"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    jz = T.JIAZI
    a = [tuple(_new_list(jz, x)[0:10]) for x in jz[0::10]]
    b = [jz[0::10][i] + T.TIAN_GAN[4:10][i] for i in range(6)]
    return _multi_get(dict(zip(a, b)), gz[3])


def _hour_zhifu_minute(year, month, day, hour, minute):
    """刻干支值符"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    jz = T.JIAZI
    a = [tuple(_new_list(jz, x)[0:10]) for x in jz[0::10]]
    b = [jz[0::10][i] + T.TIAN_GAN[4:10][i] for i in range(6)]
    return _multi_get(dict(zip(a, b)), gz[4])


def earth_plate_minute(year, month, day, hour, minute):
    """刻家地盘"""
    ke_ju = ganzhi.ju_ke(year, month, day, hour, minute)
    yinyang = ke_ju[:2]
    number = ke_ju[2]
    rotated_nums = _new_list(T.CNUMBER, number)
    gua_seq = [dict(zip(T.CNUMBER, T.EIGHT_GUA))[n] for n in rotated_nums]
    gan_seq = T.YANG_EARTH_GAN if yinyang == "陽遁" else T.YIN_EARTH_GAN
    return dict(zip(gua_seq, gan_seq))


# ── 八门 ──

def doors(year, month, day, hour, minute, option):
    """八门 (时家)"""
    ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
        year, month, day, hour, minute)
    zfzs = zhifu_n_zhishi(year, month, day, hour, minute, option)
    starting_door = zfzs.get("值使門宮")[0]
    starting_gong = zfzs.get("值使門宮")[1]
    rotate = T.CLOCKWISE_8 if ju_str[0] == "陽" else list(reversed(T.CLOCKWISE_8))

    if starting_gong == "中":
        gong_reorder = _new_list(rotate, "坤")
    else:
        gong_reorder = _new_list(rotate, starting_gong)

    if ju_str[0] == "陽":
        door_seq = _new_list(T.DOOR_ORDER, starting_door)
    else:
        door_seq = _new_list(list(reversed(T.DOOR_ORDER)), starting_door)

    return dict(zip(gong_reorder, door_seq))


def doors_minute(year, month, day, hour, minute, option):
    """八门 (刻家)"""
    ke_ju = ganzhi.ju_ke(year, month, day, hour, minute)
    zfzs = zhifu_n_zhishi_ke(year, month, day, hour, minute, option)
    starting_door = zfzs.get("值使門宮")[0]
    starting_gong = zfzs.get("值使門宮")[1]
    rotate = T.CLOCKWISE_8 if ke_ju[0] == "陽" else list(reversed(T.CLOCKWISE_8))

    if starting_gong == "中":
        gong_reorder = _new_list(rotate, "坤")
    else:
        gong_reorder = _new_list(rotate, starting_gong)

    if ke_ju[0] == "陽":
        door_seq = _new_list(T.DOOR_ORDER, starting_door)
    else:
        door_seq = _new_list(list(reversed(T.DOOR_ORDER)), starting_door)

    return dict(zip(gong_reorder, door_seq))


# ── 九星 ──

def stars(year, month, day, hour, minute, option):
    """九星 (时家)，返回 (星盘dict, 星→宫dict)"""
    ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
        year, month, day, hour, minute)
    zfzs = zhifu_n_zhishi(year, month, day, hour, minute, option)

    star_r = list("蓬任沖輔英禽柱心")
    starting_star = zfzs.get("值符星宮")[0].replace("芮", "禽")
    starting_gong = zfzs.get("值符星宮")[1]
    rotate = T.CLOCKWISE_8 if ju_str[0] == "陽" else list(reversed(T.CLOCKWISE_8))

    if ju_str[0] == "陽":
        star_seq = _new_list(star_r, starting_star)
    else:
        star_seq = _new_list(list(reversed(star_r)), starting_star)

    if starting_gong == "中":
        gong_reorder = _new_list(rotate, "坤")
    else:
        gong_reorder = _new_list(rotate, starting_gong)

    return dict(zip(gong_reorder, star_seq)), dict(zip(star_seq, gong_reorder))


def stars_minute(year, month, day, hour, minute, option):
    """九星 (刻家)"""
    ke_ju = ganzhi.ju_ke(year, month, day, hour, minute)
    zfzs = zhifu_n_zhishi_ke(year, month, day, hour, minute, option)

    star_r = list("蓬任沖輔英禽柱心")
    starting_star = zfzs.get("值符星宮")[0].replace("芮", "禽")
    starting_gong = zfzs.get("值符星宮")[1]
    rotate = T.CLOCKWISE_8 if ke_ju[0] == "陽" else list(reversed(T.CLOCKWISE_8))

    if ke_ju[0] == "陽":
        star_seq = _new_list(star_r, starting_star)
    else:
        star_seq = _new_list(list(reversed(star_r)), starting_star)

    if starting_gong == "中":
        gong_reorder = _new_list(rotate, "坤")
    else:
        gong_reorder = _new_list(rotate, starting_gong)

    return dict(zip(gong_reorder, star_seq)), dict(zip(star_seq, gong_reorder))


# ── 八神 ──

def gods(year, month, day, hour, minute, option):
    """八神 (时家)"""
    ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(
        year, month, day, hour, minute)
    zfzs = zhifu_n_zhishi(year, month, day, hour, minute, option)
    starting_gong = zfzs.get("值符星宮")[1]
    rotate = T.CLOCKWISE_8 if ju_str[0] == "陽" else list(reversed(T.CLOCKWISE_8))

    if starting_gong == "中":
        gong_reorder = _new_list(rotate, "坤")
    else:
        gong_reorder = _new_list(rotate, starting_gong)

    god_seq = T.GOD_YANG if ju_str[0] == "陽" else T.GOD_YIN
    return dict(zip(gong_reorder, god_seq))


def gods_minute(year, month, day, hour, minute, option):
    """八神 (刻家)"""
    ke_ju = ganzhi.ju_ke(year, month, day, hour, minute)
    zfzs = zhifu_n_zhishi_ke(year, month, day, hour, minute, option)
    starting_gong = zfzs.get("值符星宮")[1]
    rotate = T.CLOCKWISE_8 if ke_ju[0] == "陽" else list(reversed(T.CLOCKWISE_8))

    if starting_gong == "中":
        gong_reorder = _new_list(rotate, "坤")
    else:
        gong_reorder = _new_list(rotate, starting_gong)

    god_seq = T.GOD_YANG if ke_ju[0] == "陽" else T.GOD_YIN
    return dict(zip(gong_reorder, god_seq))


# ── 天乙 ──

def tianyi(year, month, day, hour, minute, option):
    """天乙贵人"""
    zfzs = zhifu_n_zhishi(year, month, day, hour, minute, option)
    try:
        return T.TIANYI_GUA.get(zfzs.get("值符星宮")[1])
    except (IndexError, TypeError):
        return "禽"


# ── 马星 ──

def moon_horse(year, month, day, hour, minute):
    """天马"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    zhi = gz[2][1]
    pairs = re.findall("..", "寅申卯酉辰戌巳亥午子丑未")
    d = dict(zip([tuple(p) for p in pairs], list("午申戌子寅辰")))
    return _multi_get(d, zhi)


def din_horse(year, month, day, hour, minute):
    """丁马"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    xun = ganzhi.get_xun(gz[2])
    return T.DIN_HORSE.get(xun)


def hour_horse(year, month, day, hour, minute):
    """驿马"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    zhi = gz[3][1]
    return _multi_get(T.HOUR_HORSE, zhi)


# ── 金函玉镜 (日家) ──

def gong_wangzhuai(jieqi):
    """宫旺衰"""
    wangzhuai = list("旺相胎沒死囚休廢")
    wangzhuai_num = [3, 4, 9, 2, 7, 6, 1, 8]
    wangzhuai_jieqi = {
        ('春分', '清明', '穀雨'): '春分',
        ('立夏', '小滿', '芒種'): '立夏',
        ('夏至', '小暑', '大暑'): '夏至',
        ('立秋', '處暑', '白露'): '立秋',
        ('秋分', '寒露', '霜降'): '秋分',
        ('立冬', '小雪', '大雪'): '立冬',
        ('冬至', '小寒', '大寒'): '冬至',
        ('立春', '雨水', '驚蟄'): '立春',
    }
    wzhuai = _multi_get(wangzhuai_jieqi, jieqi)
    if not wzhuai:
        return {}
    wz = dict(zip([T.JIEQI_NAME[i] for i in range(0, 24, 3)], wangzhuai_num)).get(wzhuai)
    if wz is None:
        return {}
    return dict(zip(_new_list(wangzhuai_num, wz), wangzhuai))


def gpan_star(year, month, day, hour, minute):
    """日家奇门九星"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    jieqi = ganzhi.jq(year, month, day, hour, minute)
    dgz = gz[2]

    start_jia = T.JIAZI[0::10]
    dd = [tuple(_new_list(T.JIAZI, i)[0:10]) for i in start_jia]
    shun = _multi_get(dict(zip(dd, start_jia)), dgz)

    # 与原版一致: jieqi_name[0:12]→冬至(阳遁), jieqi_name[12:24]→夏至(阴遁)
    yy = _multi_get(
        {tuple(T.JIEQI_NAME[0:12]): "冬至", tuple(T.JIEQI_NAME[12:24]): "夏至"},
        jieqi
    )
    if not shun or not yy:
        return {}

    golen_d = re.findall("..", "太乙攝提軒轅招搖天符青龍咸池太陰天乙")
    dh_doors = {"冬至": "艮離坎坤震巽", "夏至": "坤離巽坤離兌"}

    gong = dict(zip(start_jia, dh_doors.get(yy, ""))).get(shun)
    if not gong:
        return {}

    close_ten_day = _new_list(T.JIAZI, shun)[0:10]
    a_gong = _new_list(list(reversed(T.EIGHT_GUA)), gong)
    r_gua = list(reversed(T.EIGHT_GUA))

    new_dict = {**dict(zip(close_ten_day, _new_list(r_gua, gong))),
                **{close_ten_day[-1]: a_gong[0]}}
    new_dict_r = {**dict(zip(close_ten_day, _new_list(T.EIGHT_GUA, gong))),
                  **{close_ten_day[-1]: a_gong[0]}}

    ying = dict(zip(_new_list(T.EIGHT_GUA, new_dict.get(dgz)), golen_d))
    yang = dict(zip(_new_list(T.EIGHT_GUA, new_dict_r.get(dgz)), golen_d))

    # 原版: yy="冬至"→yang(阳遁), yy="夏至"→ying(阴遁)
    # 因为 new_dict_r 是正序旋转 = 阳, new_dict 是反序旋转 = 阴
    # 但原版实际: {"陰遁":ying, "陽遁":yang}.get(yy)
    # yy 经过 {"冬至":"陽遁","夏至":"陰遁"} 转换后就是 "陽遁" or "陰遁"
    # 而这里 yy 还是 "冬至"/"夏至", 所以原版用的是 {"陰遁":ying, "陽遁":yang}
    # 但 yy="冬至" → 这不是 "陰遁" 也不是 "陽遁"... 所以 get(yy) 返回 None!
    # 等等让我再看原版
    # 原版 gpan 中: yy = {"冬至":"陽遁", "夏至":"陰遁"}.get(...)
    # 所以 yy 已经是 "陽遁" 或 "陰遁" 了！
    # 我这里的 yy 还是 "冬至"/"夏至"，需要先转换
    yinyang = {"冬至": "陽遁", "夏至": "陰遁"}.get(yy, "陽遁")
    return {"陰遁": ying, "陽遁": yang}.get(yinyang, yang)


def gpan_doors(year, month, day, hour, minute):
    """日家奇门八门"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    jieqi = ganzhi.jq(year, month, day, hour, minute)
    dgz = gz[2]

    yy_raw = _multi_get(
        {tuple(T.JIEQI_NAME[0:12]): "冬至", tuple(T.JIEQI_NAME[12:24]): "夏至"},
        jieqi
    )
    yinyang = {"冬至": "陽遁", "夏至": "陰遁"}.get(yy_raw, "陽遁")

    g = []
    yy_gua = {
        "陰遁": list(reversed(T.CLOCKWISE_8)),
        "陽遁": T.CLOCKWISE_8,
    }
    for i in list("坎坤震巽乾兌艮離"):
        c = dict(zip(_new_list(yy_gua.get(yinyang, T.CLOCKWISE_8), i), T.DOOR_ORDER))
        g.append(c)

    # 按60甲子每3个分组映射
    triple_list = [i * 3 for i in range(21)]
    b = []
    for i in range(len(triple_list)):
        try:
            a = tuple(T.JIAZI[triple_list[i]:triple_list[i + 1]])
            b.append(a)
        except IndexError:
            pass

    import itertools
    ddd = _multi_get(dict(zip(b, itertools.cycle(g))), dgz)
    if ddd:
        return {**ddd, **{"中": ""}}
    return {}


def gpan_gods(year, month, day, hour, minute):
    """日家奇门八神"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    dgz = gz[2]
    return _get_gtw().get(dgz[0])


def _get_gtw():
    """日家八神表"""
    gtw = re.findall("..", "地籥六賊五符天曹地符風伯雷公雨師風雲唐符國印天關")
    gg = re.findall("..", "地籥天關唐符風雲唐符風雲雷公風伯天曹五符")
    newmap = [_new_list(gtw, i) for i in gg]
    newgtw_list = [dict(zip(T.DI_ZHI, y)) for y in newmap]
    return dict(zip(T.TIAN_GAN, newgtw_list))


def crane_god():
    """鹤神"""
    d = list("巽離坤兌乾坎天艮震")[:8]
    dd = [6, 5, 6, 5, 6, 5, 16, 6]
    newc_list = [[d[i]] * dd[i] for i in range(8)]
    return dict(zip(_new_list(T.JIAZI, "庚申"), newc_list))


def gpan(year, month, day, hour, minute):
    """金函玉镜日家奇门完整排盘"""
    gz = ganzhi.gangzhi(year, month, day, hour, minute)
    jieqi = ganzhi.jq(year, month, day, hour, minute)
    dgz = gz[2]
    gzd = f"{gz[0]}年{gz[1]}月{gz[2]}日{gz[3]}時"

    start_jia = T.JIAZI[0::10]
    dd = [tuple(_new_list(T.JIAZI, i)[0:10]) for i in start_jia]
    shun = _multi_get(dict(zip(dd, start_jia)), dgz)

    # 与原版一致: jieqi_name[0:12]→冬至(阳遁), jieqi_name[12:24]→夏至(阴遁)
    yy_raw = _multi_get(
        {tuple(T.JIEQI_NAME[0:12]): "冬至", tuple(T.JIEQI_NAME[12:24]): "夏至"},
        jieqi
    )
    yinyang = {"冬至": "陽遁", "夏至": "陰遁"}.get(yy_raw, "")

    if not yinyang:
        return {}

    star = gpan_star(year, month, day, hour, minute)
    door = gpan_doors(year, month, day, hour, minute)
    god = gpan_gods(year, month, day, hour, minute)

    crane = crane_god().get(dgz)

    return {
        "排盤方式": "金函玉鏡",
        "干支": gzd,
        "旬首": ganzhi.xun_shou(dgz),
        "旬空": ganzhi.daykong_shikong(year, month, day, hour, minute),
        "局日": ganzhi.ju_day(year, month, day, hour, minute),
        "排局": f"{yinyang}{dgz}日",
        "節氣": jieqi,
        "天乙": tianyi(year, month, day, hour, minute, 1),
        "鶴神": crane,
        "星": star,
        "門": door,
        "神": god,
        "馬星": {
            "天馬": moon_horse(year, month, day, hour, minute),
            "丁馬": din_horse(year, month, day, hour, minute),
            "驛馬": hour_horse(year, month, day, hour, minute),
        },
    }
