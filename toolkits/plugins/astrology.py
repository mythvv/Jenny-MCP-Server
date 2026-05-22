"""
Astrology 工具包 - 占星计算

基于 Kerykeion 库提供 5 个工具：
- natal_chart: 本命盘（行星位置、宫位、相位）
- horoscope: 每日运势（当前天象与星座关系）
- synastry: 合盘/配对（两人星盘交叉相位）
- retrogrades: 逆行查询（当前各行星逆行状态）
- moon_phase: 月相查询（月相、月亮星座、illumination）
"""

import json
import math
from datetime import datetime, timezone
from typing import Optional

from kerykeion import AstrologicalSubjectFactory, SynastryAspects

from toolkits.base import BaseToolkit

SIGN_NAMES_CN = {
    "Ari": "白羊座", "Tau": "金牛座", "Gem": "双子座", "Can": "巨蟹座",
    "Leo": "狮子座", "Vir": "处女座", "Lib": "天秤座", "Sco": "天蝎座",
    "Sag": "射手座", "Cap": "摩羯座", "Aqu": "水瓶座", "Pis": "双鱼座",
}

SIGN_NAMES_EN = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}

PLANET_NAMES_CN = {
    "Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星",
    "Mars": "火星", "Jupiter": "木星", "Saturn": "土星",
    "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星",
}

HOUSE_NAME_TO_NUM = {
    "First_House": 1, "Second_House": 2, "Third_House": 3, "Fourth_House": 4,
    "Fifth_House": 5, "Sixth_House": 6, "Seventh_House": 7, "Eighth_House": 8,
    "Ninth_House": 9, "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
}

PLANET_ATTRS = ["sun", "moon", "mercury", "venus", "mars",
                "jupiter", "saturn", "uranus", "neptune", "pluto"]

HOUSE_ORDER = ["first", "second", "third", "fourth", "fifth", "sixth",
               "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]

ASPECT_NAMES_CN = {
    "conjunction": "合相", "opposition": "对冲", "trine": "三合",
    "sextile": "六合", "square": "刑相", "quincunx": "梅花",
    "semisextile": "半六合", "quintile": "五分相",
}

SIGN_RANGE = {
    "Ari": (0, 30), "Tau": (30, 60), "Gem": (60, 90), "Can": (90, 120),
    "Leo": (120, 150), "Vir": (150, 180), "Lib": (180, 210), "Sco": (210, 240),
    "Sag": (240, 270), "Cap": (270, 300), "Aqu": (300, 330), "Pis": (330, 360),
}


def _sign_cn(sign_short: str) -> str:
    return SIGN_NAMES_CN.get(sign_short, sign_short)


def _sign_en(sign_short: str) -> str:
    return SIGN_NAMES_EN.get(sign_short, sign_short)


def _deg_min(position: float) -> str:
    deg = int(position) % 30
    minutes = int((position % 1) * 60)
    return f"{deg}°{minutes:02d}'"


def _parse_birth_data(birth_date: str, birth_time: str, latitude: float,
                      longitude: float, tz_str: str = "Asia/Shanghai"):
    parts = birth_date.split("-")
    latitude, longitude = float(latitude), float(longitude)
    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    time_parts = birth_time.split(":")
    hour, minute = int(time_parts[0]), int(time_parts[1])
    return AstrologicalSubjectFactory.from_birth_data(
        "Subject", year, month, day, hour, minute,
        lng=longitude, lat=latitude, tz_str=tz_str, online=False,
    )


def _planet_info(subject, attr: str) -> dict:
    p = getattr(subject, attr)
    return {
        "name": attr.capitalize(),
        "name_cn": PLANET_NAMES_CN.get(attr.capitalize(), attr),
        "sign": _sign_en(p.sign),
        "sign_cn": _sign_cn(p.sign),
        "degree": round(p.position, 2),
        "degree_display": _deg_min(p.position),
        "house": HOUSE_NAME_TO_NUM.get(p.house, 0) if p.house else None,
        "retrograde": p.retrograde or False,
        "element": p.element if hasattr(p, "element") else None,
        "quality": p.quality if hasattr(p, "quality") else None,
    }


class AstrologyToolkit(BaseToolkit):
    """Astrology 工具包 - 占星计算"""

    name = "astrology"
    description = "占星工具包 - 本命盘/每日运势/合盘配对/逆行查询/月相查询"

    def get_config_schema(self) -> dict:
        return {}

    def get_tools(self):
        return [
            (self.natal_chart, "natal_chart",
             "计算本命盘：太阳/月亮/上升星座、10颗行星位置与落宫、主要相位。返回结构化数据供AI解读。",
             [("birth_date", "str", None, "出生日期 YYYY-MM-DD"),
              ("birth_time", "str", None, "出生时间 HH:MM（24小时制）"),
              ("latitude", "float", None, "出生地纬度"),
              ("longitude", "float", None, "出生地经度"),
              ("timezone", "str", "Asia/Shanghai", "时区，如 Asia/Shanghai, Europe/London, America/New_York")]),
            (self.horoscope, "horoscope",
             "每日运势：基于当前天象与指定星座的相位关系，返回行星过境和逆行信息。",
             [("sun_sign", "str", None, "太阳星座（英文如 Aries/Taurus/Gemini 或中文如 白羊座/金牛座）"),
              ("date", "Optional[str]", None, "日期 YYYY-MM-DD，不传默认今天")]),
            (self.synastry, "synastry",
             "合盘/配对分析：计算两人星盘的交叉相位、宫位叠加和兼容性评分。",
             [("person1", "str", None, "第一人信息 JSON：{\"birth_date\":\"YYYY-MM-DD\",\"birth_time\":\"HH:MM\",\"latitude\":float,\"longitude\":float,\"timezone\":\"Asia/Shanghai\"}"),
              ("person2", "str", None, "第二人信息 JSON（同上格式）")]),
            (self.retrogrades, "retrogrades",
             "逆行查询：返回指定日期前后所有行星逆行状态和变化。",
             [("date", "Optional[str]", None, "日期 YYYY-MM-DD，不传默认今天")]),
            (self.moon_phase, "moon_phase",
             "月相查询：返回指定日期的月相信息（新月/上弦/满月/下弦等）。",
             [("date", "Optional[str]", None, "日期 YYYY-MM-DD，不传默认今天")]),
        ]

    async def natal_chart(self, birth_date: str, birth_time: str,
                          latitude: float, longitude: float,
                          timezone: str = "Asia/Shanghai") -> dict:
        """计算本命盘：太阳/月亮/上升星座、行星位置与落宫、主要相位"""
        try:
            subject = _parse_birth_data(birth_date, birth_time, latitude, longitude, timezone)
        except Exception as e:
            return {"error": f"出生数据解析失败: {e}"}

        planets = [_planet_info(subject, attr) for attr in PLANET_ATTRS]

        houses = []
        for i, name in enumerate(HOUSE_ORDER, 1):
            h = getattr(subject, f"{name}_house")
            houses.append({
                "house": i,
                "sign": _sign_en(h.sign),
                "sign_cn": _sign_cn(h.sign),
                "cusp_degree": round(h.position, 2),
                "cusp_abs_pos": round(h.abs_pos, 2),
            })

        asc = subject.first_house
        mc = subject.tenth_house

        sun_info = _planet_info(subject, "sun")
        moon_info = _planet_info(subject, "moon")

        natal_aspects = []
        try:
            from kerykeion import NatalAspects
            na = NatalAspects(subject)
            for a in na.relevant_aspects:
                a_dict = json.loads(a.model_dump_json())
                if a_dict.get("orbit", 10) <= 10:
                    natal_aspects.append({
                        "body1": a_dict["p1_name"],
                        "body2": a_dict["p2_name"],
                        "aspect": a_dict["aspect"],
                        "aspect_cn": ASPECT_NAMES_CN.get(a_dict["aspect"], a_dict["aspect"]),
                        "orb": round(a_dict["orbit"], 2),
                    })
        except Exception:
            pass

        return {
            "birth_date": birth_date,
            "birth_time": birth_time,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "sun": {"sign": sun_info["sign"], "sign_cn": sun_info["sign_cn"],
                    "degree_display": sun_info["degree_display"]},
            "moon": {"sign": moon_info["sign"], "sign_cn": moon_info["sign_cn"],
                     "degree_display": moon_info["degree_display"]},
            "ascendant": {"sign": _sign_en(asc.sign), "sign_cn": _sign_cn(asc.sign),
                          "degree": round(asc.position, 2)},
            "midheaven": {"sign": _sign_en(mc.sign), "sign_cn": _sign_cn(mc.sign),
                          "degree": round(mc.position, 2)},
            "planets": planets,
            "houses": houses,
            "aspects": natal_aspects[:20],
        }

    async def horoscope(self, sun_sign: str, date: Optional[str] = None) -> dict:
        """每日运势：基于当前天象与指定星座的关系"""
        try:
            sign_key = None
            for short, en in SIGN_NAMES_EN.items():
                if en.lower() == sun_sign.lower() or SIGN_NAMES_CN.get(short, "") == sun_sign or short.lower() == sun_sign.lower()[:3]:
                    sign_key = short
                    break
            if not sign_key:
                return {"error": f"未知星座: {sun_sign}. 可用: {', '.join(SIGN_NAMES_EN.values())}"}

            if date:
                dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            transit = AstrologicalSubjectFactory.from_birth_data(
                "Today", dt.year, dt.month, dt.day, 12, 0,
                lng=0, lat=51.5, tz_str="UTC", online=False,
            )

            sign_start, sign_end = SIGN_RANGE[sign_key]
            sign_mid = (sign_start + sign_end) / 2

            transits = []
            for attr in PLANET_ATTRS:
                p = getattr(transit, attr)
                planet_lon = p.abs_pos
                diff = abs(planet_lon - sign_mid)
                if diff > 180:
                    diff = 360 - diff

                major_aspects = []
                for asp_name, asp_deg in [("conjunction", 0), ("sextile", 60), ("square", 90),
                                           ("trine", 120), ("opposition", 180)]:
                    orb = abs(diff - asp_deg)
                    if orb <= 8:
                        major_aspects.append({
                            "aspect": asp_name,
                            "aspect_cn": ASPECT_NAMES_CN[asp_name],
                            "orb": round(orb, 2),
                            "applying": True,
                        })

                if major_aspects:
                    transits.append({
                        "planet": attr.capitalize(),
                        "planet_cn": PLANET_NAMES_CN.get(attr.capitalize(), attr),
                        "sign": _sign_en(p.sign),
                        "sign_cn": _sign_cn(p.sign),
                        "retrograde": p.retrograde or False,
                        "aspects_to_sign": major_aspects,
                    })

            retrogrades = []
            for attr in PLANET_ATTRS:
                p = getattr(transit, attr)
                if p.retrograde:
                    retrogrades.append(PLANET_NAMES_CN.get(attr.capitalize(), attr))

            moon_info = {
                "sign": _sign_en(transit.moon.sign),
                "sign_cn": _sign_cn(transit.moon.sign),
                "degree": round(transit.moon.position, 2),
            }

            return {
                "sun_sign": _sign_en(sign_key),
                "sun_sign_cn": _sign_cn(sign_key),
                "date": dt.strftime("%Y-%m-%d"),
                "transits": transits,
                "retrogrades": retrogrades,
                "moon": moon_info,
            }
        except Exception as e:
            return {"error": f"运势计算失败: {e}"}

    async def synastry(self, person1, person2) -> dict:
        """合盘/配对分析：两人星盘交叉相位和宫位叠加"""
        try:
            import json as _json
            if isinstance(person1, str):
                person1 = _json.loads(person1)
            if isinstance(person2, str):
                person2 = _json.loads(person2)
            p1 = _parse_birth_data(
                person1["birth_date"], person1["birth_time"],
                person1["latitude"], person1["longitude"],
                person1.get("timezone", "Asia/Shanghai"),
            )
            p2 = _parse_birth_data(
                person2["birth_date"], person2["birth_time"],
                person2["latitude"], person2["longitude"],
                person2.get("timezone", "Asia/Shanghai"),
            )
        except Exception as e:
            return {"error": f"出生数据解析失败: {e}"}

        p1_sun = _planet_info(p1, "sun")
        p1_moon = _planet_info(p1, "moon")
        p1_asc = {"sign": _sign_en(p1.first_house.sign),
                   "sign_cn": _sign_cn(p1.first_house.sign)}

        p2_sun = _planet_info(p2, "sun")
        p2_moon = _planet_info(p2, "moon")
        p2_asc = {"sign": _sign_en(p2.first_house.sign),
                   "sign_cn": _sign_cn(p2.first_house.sign)}

        cross_aspects = []
        try:
            sa = SynastryAspects(p1, p2)
            for a in sa.relevant_aspects:
                a_dict = json.loads(a.model_dump_json())
                cross_aspects.append({
                    "person1_planet": a_dict["p1_name"],
                    "person1_planet_cn": PLANET_NAMES_CN.get(a_dict["p1_name"], a_dict["p1_name"]),
                    "person2_planet": a_dict["p2_name"],
                    "person2_planet_cn": PLANET_NAMES_CN.get(a_dict["p2_name"], a_dict["p2_name"]),
                    "aspect": a_dict["aspect"],
                    "aspect_cn": ASPECT_NAMES_CN.get(a_dict["aspect"], a_dict["aspect"]),
                    "orb": round(a_dict["orbit"], 2),
                })
        except Exception:
            pass

        harmonious = sum(1 for a in cross_aspects
                         if a["aspect"] in ("trine", "sextile", "conjunction"))
        tense = sum(1 for a in cross_aspects
                    if a["aspect"] in ("opposition", "square"))
        total = harmonious + tense
        harmony_score = round(harmonious / total, 2) if total > 0 else 0.5

        p2_cusps = [getattr(p2, f"{HOUSE_ORDER[j]}_house").abs_pos for j in range(12)]
        p1_in_p2 = []
        for attr in PLANET_ATTRS:
            p = getattr(p1, attr)
            house_num = _find_house(p.abs_pos, p2_cusps)
            p1_in_p2.append({
                "planet": PLANET_NAMES_CN.get(attr.capitalize(), attr),
                "house": house_num,
            })

        p1_cusps = [getattr(p1, f"{HOUSE_ORDER[j]}_house").abs_pos for j in range(12)]
        p2_in_p1 = []
        for attr in PLANET_ATTRS:
            p = getattr(p2, attr)
            house_num = _find_house(p.abs_pos, p1_cusps)
            p2_in_p1.append({
                "planet": PLANET_NAMES_CN.get(attr.capitalize(), attr),
                "house": house_num,
            })

        return {
            "person1": {
                "sun": p1_sun["sign_cn"],
                "moon": p1_moon["sign_cn"],
                "ascendant": p1_asc["sign_cn"],
            },
            "person2": {
                "sun": p2_sun["sign_cn"],
                "moon": p2_moon["sign_cn"],
                "ascendant": p2_asc["sign_cn"],
            },
            "cross_aspects": cross_aspects,
            "person1_planets_in_person2_houses": p1_in_p2,
            "person2_planets_in_person1_houses": p2_in_p1,
            "harmony_score": harmony_score,
            "harmonious_aspects": harmonious,
            "tense_aspects": tense,
        }

    async def retrogrades(self, date: Optional[str] = None) -> dict:
        """查询指定日期各行星逆行状态"""
        try:
            if date:
                dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            transit = AstrologicalSubjectFactory.from_birth_data(
                "Transit", dt.year, dt.month, dt.day, 12, 0,
                lng=0, lat=51.5, tz_str="UTC", online=False,
            )

            retro_list = []
            direct_list = []
            for attr in PLANET_ATTRS:
                p = getattr(transit, attr)
                info = {
                    "planet": attr.capitalize(),
                    "planet_cn": PLANET_NAMES_CN.get(attr.capitalize(), attr),
                    "sign": _sign_en(p.sign),
                    "sign_cn": _sign_cn(p.sign),
                    "degree": round(p.position, 2),
                    "retrograde": p.retrograde or False,
                }
                if info["retrograde"]:
                    retro_list.append(info)
                else:
                    direct_list.append(info)

            return {
                "date": dt.strftime("%Y-%m-%d"),
                "retrograde": retro_list,
                "direct": direct_list,
            }
        except Exception as e:
            return {"error": f"逆行查询失败: {e}"}

    async def moon_phase(self, date: Optional[str] = None) -> dict:
        """查询月相：月相名称、月亮星座、光照百分比"""
        try:
            if date:
                dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            transit = AstrologicalSubjectFactory.from_birth_data(
                "Transit", dt.year, dt.month, dt.day, 12, 0,
                lng=0, lat=51.5, tz_str="UTC", online=False,
            )

            moon_lon = transit.moon.abs_pos
            sun_lon = transit.sun.abs_pos
            phase_angle = (moon_lon - sun_lon) % 360
            illumination = round((1 - math.cos(math.radians(phase_angle))) / 2, 4)

            if phase_angle < 22.5 or phase_angle >= 337.5:
                phase_name = "新月"
                phase_name_en = "New Moon"
                emoji = "🌑"
            elif phase_angle < 67.5:
                phase_name = "峨眉月"
                phase_name_en = "Waxing Crescent"
                emoji = "🌒"
            elif phase_angle < 112.5:
                phase_name = "上弦月"
                phase_name_en = "First Quarter"
                emoji = "🌓"
            elif phase_angle < 157.5:
                phase_name = "盈凸月"
                phase_name_en = "Waxing Gibbous"
                emoji = "🌔"
            elif phase_angle < 202.5:
                phase_name = "满月"
                phase_name_en = "Full Moon"
                emoji = "🌕"
            elif phase_angle < 247.5:
                phase_name = "亏凸月"
                phase_name_en = "Waning Gibbous"
                emoji = "🌖"
            elif phase_angle < 292.5:
                phase_name = "下弦月"
                phase_name_en = "Last Quarter"
                emoji = "🌗"
            else:
                phase_name = "残月"
                phase_name_en = "Waning Crescent"
                emoji = "🌘"

            return {
                "date": dt.strftime("%Y-%m-%d"),
                "moon_sign": _sign_en(transit.moon.sign),
                "moon_sign_cn": _sign_cn(transit.moon.sign),
                "moon_degree": round(transit.moon.position, 2),
                "phase": phase_name,
                "phase_en": phase_name_en,
                "phase_angle": round(phase_angle, 2),
                "illumination": illumination,
                "emoji": emoji,
            }
        except Exception as e:
            return {"error": f"月相查询失败: {e}"}


def _find_house(planet_abs_pos: float, cusps: list) -> int:
    """根据宫头位置判断行星落入哪个宫位（Placidus）"""
    n = len(cusps)
    for i in range(n):
        next_i = (i + 1) % n
        start = cusps[i]
        end = cusps[next_i]
        if start > end:
            if planet_abs_pos >= start or planet_abs_pos < end:
                return i + 1
        else:
            if start <= planet_abs_pos < end:
                return i + 1
    return 1
