"""
奇门遁甲 — 干支计算层

依赖: sxtwl, ephem
"""

import re
import math
import datetime
from itertools import cycle
from sxtwl import fromSolar
import ephem

from . import tables as T


# ── 通用工具 ──

def _new_list(lst, start):
    """旋转列表，使 start 成为第一个元素"""
    idx = lst.index(start)
    return lst[idx:] + lst[:idx]


def _new_list_r(lst, start):
    """逆序旋转列表"""
    idx = lst.index(start)
    result = []
    for i in range(len(lst)):
        result.append(lst[idx % len(lst)])
        idx -= 1
    return result


def _multi_get(d, key):
    """在 key 为 tuple 的 dict 中查找"""
    for keys, v in d.items():
        if key in keys:
            return v
    return None


# ── 六十甲子 ──

def jiazi():
    return T.JIAZI


# ── 六甲旬首 ──

def liujia_dict():
    """返回 {六甲旬首: (甲子组, ...)} → 旬首名"""
    jz = T.JIAZI
    groups = [tuple(jz[i*10:(i+1)*10]) for i in range(6)]
    return dict(zip(groups, jz[0::10]))


def get_xun(gz_str):
    """给定一个干支，返回其所在的六甲旬首"""
    return _multi_get(liujia_dict(), gz_str)


# ── 五虎遁 (年起月柱) ──

def lunar_month_ganzhi(year_ganzhi, lunar_month):
    """年干支 → 12 个月的月柱干支 (五虎遁)"""
    start = _multi_get(T.WUHU, year_ganzhi[0])
    if start is None:
        start = _multi_get(T.WUHU, year_ganzhi[1])
    months = _new_list(T.JIAZI, start)[:12]
    return dict(zip(range(1, 13), months)).get(lunar_month)


# ── 五鼠遁 (日起时柱) ──

def hour_ganzhi(day_ganzhi):
    """日干支 → 12 个时辰的干支 (五鼠遁)"""
    # 先尝试天干 (day[0])，再尝试地支 (day[1])
    start = _multi_get(T.WUSHU, day_ganzhi[0])
    if start is None:
        start = _multi_get(T.WUSHU, day_ganzhi[1])
    hours = _new_list(T.JIAZI, start)[:12]
    return dict(zip(list(T.DI_ZHI), hours))


# ── 五马遁 (时起刻柱) ──

def ke_ganzhi(hour_ganzhi):
    """时干支 → 10刻的干支 (五马遁)"""
    start = _multi_get(T.WUMA, hour_ganzhi[0])
    if start is None:
        start = _multi_get(T.WUMA, hour_ganzhi[1])
    return _new_list(T.JIAZI, start)


def ke_jiazi_dict(hour_ganzhi):
    """时干支 → 每十分钟一个干支 (五马遁, 60甲子循环)"""
    base = ke_ganzhi(hour_ganzhi)
    result = {}
    for h in range(24):
        for m_idx in range(6):
            key = f"{h}:{m_idx}0"
            result[key] = base[(h * 6 + m_idx) % 60]
    return result


# ── 干支计算 (四柱) ──

def _ephem_date(year, month, day, hour):
    """构建 ephem.Date，处理 23 时跨日"""
    if hour == 23:
        return ephem.Date(round(ephem.Date(
            f"{year:04d}/{month:02d}/{(day+1):02d} 00:00:00.00"
        ), 3))
    return ephem.Date(f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:00:00.00")


def gangzhi(year, month, day, hour, minute):
    """
    返回四柱干支 + 刻干支
    [年柱, 月柱, 日柱, 时柱, 刻柱]
    """
    d = _ephem_date(year, month, day, hour)
    dd = list(d.tuple())
    cdate = fromSolar(dd[0], dd[1], dd[2])

    yTG = f"{T.TIAN_GAN[cdate.getYearGZ().tg]}{T.DI_ZHI[cdate.getYearGZ().dz]}"
    mTG = f"{T.TIAN_GAN[cdate.getMonthGZ().tg]}{T.DI_ZHI[cdate.getMonthGZ().dz]}"
    dTG = f"{T.TIAN_GAN[cdate.getDayGZ().tg]}{T.DI_ZHI[cdate.getDayGZ().dz]}"
    hTG = f"{T.TIAN_GAN[cdate.getHourGZ(dd[3]).tg]}{T.DI_ZHI[cdate.getHourGZ(dd[3]).dz]}"

    # 年 < 1900 时需手动计算月柱
    if year < 1900:
        lunar = fromSolar(year, month, day)
        mTG = lunar_month_ganzhi(yTG, lunar.getLunarMonth())

    # 时柱用五鼠遁校正
    hTG_corrected = hour_ganzhi(dTG).get(hTG[1])

    # 刻柱
    zi_hour = gangzhi_raw(year, month, day, 0, 0)[3]
    minute_key = f"{hour}:{(minute // 10) * 10:02d}"
    ke_gz = ke_jiazi_dict(zi_hour).get(minute_key, hTG_corrected)

    return [yTG, mTG, dTG, hTG_corrected, ke_gz]


def gangzhi_raw(year, month, day, hour, minute):
    """返回原始四柱(不计算刻干支)"""
    d = _ephem_date(year, month, day, hour)
    dd = list(d.tuple())
    cdate = fromSolar(dd[0], dd[1], dd[2])

    yTG = f"{T.TIAN_GAN[cdate.getYearGZ().tg]}{T.DI_ZHI[cdate.getYearGZ().dz]}"
    mTG = f"{T.TIAN_GAN[cdate.getMonthGZ().tg]}{T.DI_ZHI[cdate.getMonthGZ().dz]}"
    dTG = f"{T.TIAN_GAN[cdate.getDayGZ().tg]}{T.DI_ZHI[cdate.getDayGZ().dz]}"
    hTG = f"{T.TIAN_GAN[cdate.getHourGZ(dd[3]).tg]}{T.DI_ZHI[cdate.getHourGZ(dd[3]).dz]}"

    if year < 1900:
        lunar = fromSolar(year, month, day)
        mTG = lunar_month_ganzhi(yTG, lunar.getLunarMonth())

    hTG_corrected = hour_ganzhi(dTG).get(hTG[1])
    return [yTG, mTG, dTG, hTG_corrected]


# ── 旬首 ──

def xun_shou(gz_str):
    """干支 → 旬首遁干"""
    d1 = dict(zip(T.DI_ZHI, list(range(1, 13)))).get(gz_str[1])
    d2 = dict(zip(T.TIAN_GAN, list(range(1, 11)))).get(gz_str[0])
    diff = d1 - d2
    if diff < 0:
        diff += 12
    return {0: "戊", 10: "己", 8: "庚", 6: "辛", 4: "壬", 2: "癸"}.get(diff)


# ── 空亡 ──

def daykong_shikong(year, month, day, hour, minute):
    """返回日空和时空"""
    gz = gangzhi(year, month, day, hour, minute)
    dk_xun = get_xun(gz[2])
    sk_xun = get_xun(gz[3])
    return {
        "日空": T.LIUJIA_KONG.get(dk_xun, ""),
        "時空": T.LIUJIA_KONG.get(sk_xun, ""),
    }


def hourkong_minutekong(year, month, day, hour, minute):
    """返回时空(时柱)和刻空"""
    gz = gangzhi(year, month, day, hour, minute)
    g3_xun = get_xun(gz[3])
    g4_xun = get_xun(gz[4])
    return {
        "日空": T.LIUJIA_KONG.get(g3_xun, ""),
        "時空": T.LIUJIA_KONG.get(g4_xun, ""),
    }


# ── 节气 ──

def _ecliptic_lon(jd_utc):
    s = ephem.Sun(jd_utc)
    equ = ephem.Equatorial(s.ra, s.dec, epoch=jd_utc)
    e = ephem.Ecliptic(equ)
    return e.lon


def _sta(jd):
    e = _ecliptic_lon(jd)
    return int(e * 180.0 / math.pi / 15)


def _iteration(jd):
    """迭代找到节气交界时刻"""
    s1 = _sta(jd)
    s0 = s1
    dt = 1.0
    while True:
        jd += dt
        s = _sta(jd)
        if s0 != s:
            s0 = s
            dt = -dt / 2
        if abs(dt) < 0.0000001 and s != s1:
            break
    return jd


def _change_date(year, month, day, hour, minute):
    """获取前30天的日期用于节气计算"""
    ts = ephem.Date(f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}:00")
    return ephem.Date(ts - 24 * ephem.hour * 30)


def jq(year, month, day, hour, minute):
    """计算当前节气名称"""
    current = ephem.Date(f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}:00")
    jd = _change_date(year, month, day, hour, minute)

    e = _ecliptic_lon(jd)
    n = int(e * 180.0 / math.pi / 15) + 1

    result = []
    for i in range(3):
        if n >= 24:
            n -= 24
        jd = _iteration(jd)
        d = ephem.Date(jd + 1/3).tuple()
        dt = ephem.Date(f"{d[0]:04d}/{d[1]:02d}/{d[2]:02d} {int(d[3]):02d}:{int(d[4]):02d}:00.00")
        result.append({dt: T.JIEQI_NAME[n]})
        n += 1

    times = [list(r.keys())[0] for r in result]
    if current > times[0] and current > times[1] and current > times[2]:
        return list(result[2].values())[0]
    if current > times[0] and current > times[1] and current <= times[2]:
        return list(result[1].values())[0]
    if current >= times[1] and current < times[2]:
        return list(result[1].values())[0]
    if current < times[1] and current < times[2]:
        return list(result[0].values())[0]
    return list(result[0].values())[0]


def jq_distance(year, month, day, hour, minute):
    """返回后续12个节气的时间和当前时间"""
    current = f"{year:04d}/{month:02d}/{day:02d} {hour:02d}:{minute:02d}:00"
    jd = _change_date(year, month, day, hour, minute)
    result = {}
    e = _ecliptic_lon(jd)
    n = int(e * 180.0 / math.pi / 15) + 1
    for i in range(12):
        if n >= 24:
            n -= 24
        jd = _iteration(jd)
        d = ephem.Date(jd + 1/3).tuple()
        dt = f"{d[0]:04d}/{d[1]:02d}/{d[2]:02d} {int(d[3]):02d}:{int(d[4]):02d}:00.00".split(".")[0]
        result[T.JIEQI_NAME[n]] = dt
        n += 1
    return result, current


# ── 上中下元 ──

def findyuen(year, month, day, hour, minute):
    """日干支 → 上/中/下元"""
    gz = gangzhi(year, month, day, hour, minute)
    return _findyuen_by_gz(gz[2])


def findyuen_minute(year, month, day, hour, minute):
    """刻干支 → 上/中/下元"""
    gz = gangzhi(year, month, day, hour, minute)
    return _findyuen_by_gz(gz[3])


def _findyuen_by_gz(gz_str):
    jz = T.JIAZI
    groups = [tuple(jz[i*5:(i+1)*5]) for i in range(12)]
    labels = ["上元", "中元", "下元"] * 4
    d = dict(zip(groups, labels))
    return _multi_get(d, gz_str)


# ── 局数 (拆补法) ──

def ju_chaibu(year, month, day, hour, minute):
    """拆补法 → "陽遁一局上元" 格式"""
    jieqi = jq(year, month, day, hour, minute)
    yuen = findyuen(year, month, day, hour, minute)
    ju_code = _multi_get(T.JIEQI_JU_CODE, jieqi)
    yinyang = _multi_get(T.JIEQI_YINYANG, jieqi)

    if not ju_code or not yuen or not yinyang:
        return f"{yinyang or '?'}?局{yuen or '?'}"

    ju_num = {"上元": ju_code[0], "中元": ju_code[1], "下元": ju_code[2]}.get(yuen)
    return f"{yinyang}{ju_num}局{yuen}"


# ── 局数 (置闰法) ──

def ju_zhirun(year, month, day, hour, minute):
    """置闰法 → "陽遁一局上元" 格式"""
    jieqi = jq(year, month, day, hour, minute)
    yinyang = _multi_get(T.JIEQI_YINYANG, jieqi)
    ju_code = _multi_get(T.JIEQI_JU_CODE, jieqi)

    gz = gangzhi(year, month, day, hour, minute)
    dgz = gz[2]

    # 找符头
    jz = T.JIAZI
    jlist = [tuple(jz[i*5:(i+1)*5]) for i in range(12)]
    fuhead = dict(zip(jlist, jz[0::5]))
    fd = _multi_get(fuhead, dgz)

    three_yuen = _multi_get(T.FU_TOU_YUEN, fd)
    kook = {"上元": ju_code[0], "中元": ju_code[1], "下元": ju_code[2]}.get(three_yuen) if ju_code else None

    # 判断是否符头日
    futou_days = ["甲子","甲午","己卯","己酉","甲寅","甲申","己巳","己亥","甲辰","甲戌","己丑","己未"]
    is_futou = dgz in futou_days

    # 计算与节气的距离
    dist_map, current_str = jq_distance(year, month, day, hour, minute)
    jieqi_dist = dist_map.get(jieqi)
    if jieqi_dist:
        ct = datetime.datetime.strptime(current_str, "%Y/%m/%d %H:%M:%S")
        jt = datetime.datetime.strptime(jieqi_dist, "%Y/%m/%d %H:%M:%S")
        diff = (ct - jt).days
    else:
        diff = 0

    # 超神处理
    if diff >= 9:
        new_jq = _new_list(T.JIEQI_NAME, jieqi)[1]
        new_code = _multi_get(T.JIEQI_JU_CODE, new_jq)
        if new_code and three_yuen:
            kook = {"上元": new_code[0], "中元": new_code[1], "下元": new_code[2]}.get(three_yuen)
        yinyang = _multi_get(T.JIEQI_YINYANG, new_jq)

    return f"{yinyang}{kook}局{three_yuen}"


# ── 局数 (刻家) ──

def ju_ke(year, month, day, hour, minute):
    """刻家局数"""
    gz = gangzhi(year, month, day, hour, minute)
    hgz = gz[3]

    yinyang = _multi_get(
        {tuple("子丑寅卯辰巳"): "陽遁", tuple("午未申酉戌亥"): "陰遁"},
        hgz[1]
    )
    qu = _multi_get(T.JIEQI_KE_CODE, jq(year, month, day, hour, minute))
    yuen = findyuen_minute(year, month, day, hour, minute)
    idx = {"上元": 0, "中元": 1, "下元": 2}.get(yuen, 0)
    return f"{yinyang}{qu[idx]}局{yuen}"


# ── 解析局数字符串 ──

def parse_ju(ju_str):
    """'陽遁一局上元' → (yinyang='陽遁', number='一', yuen='上元')"""
    yinyang = ju_str[:2] if ju_str[:2] in ("陽遁", "陰遁") else ju_str[0]
    number = ju_str[2] if len(ju_str) > 2 else "一"
    yuen = ju_str[4:] if len(ju_str) > 4 else "上元"
    return yinyang, number, yuen


# ── 日干局日 ──

def ju_day(year, month, day, hour, minute):
    gz = gangzhi(year, month, day, hour, minute)
    try:
        return _multi_get(T.JU_DAY, gz[2][0])
    except (TypeError, IndexError):
        return _multi_get(T.JU_DAY, gz[2][1])
