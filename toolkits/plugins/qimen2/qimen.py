"""
奇门遁甲 — Qimen 主类 Pipeline 编排
"""

from . import ganzhi
from . import plates
from . import stages


class Qimen:
    """奇门遁甲排盘"""

    def __init__(self, year, month, day, hour, minute):
        self.year = int(year)
        self.month = int(month)
        self.day = int(day)
        self.hour = int(hour)
        self.minute = int(minute)

    def _args(self):
        return (self.year, self.month, self.day, self.hour, self.minute)

    # ── 时家奇门 ──

    def pan(self, option=1):
        """
        时家奇门起盘
        option: 1=拆补, 2=置闰
        """
        args = self._args()
        gz = ganzhi.gangzhi(*args)
        gzd = f"{gz[0]}年{gz[1]}月{gz[2]}日{gz[3]}時"

        ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(*args)
        shunhead = ganzhi.xun_shou(gz[2])
        shunkong = ganzhi.daykong_shikong(*args)
        jieqi = ganzhi.jq(*args)
        zfzs = plates.zhifu_n_zhishi(*args, option)

        star_result = plates.stars(*args, option)
        star = star_result[0]
        door = plates.doors(*args, option)
        god = plates.gods(*args, option)

        return {
            "排盤方式": {1: "拆補", 2: "置閏"}.get(option),
            "干支": gzd,
            "旬首": shunhead,
            "旬空": shunkong,
            "局日": ganzhi.ju_day(*args),
            "排局": ju_str,
            "節氣": jieqi,
            "值符值使": zfzs,
            "天乙": plates.tianyi(*args, option),
            "天盤": plates.sky_plate(*args, option),
            "地盤": plates.earth_plate(ju_str),
            "門": door,
            "星": star,
            "神": god,
            "馬星": {
                "天馬": plates.moon_horse(*args),
                "丁馬": plates.din_horse(*args),
                "驛馬": plates.hour_horse(*args),
            },
            "長生運": stages.twelve_stages(*args, option),
        }

    # ── 刻家奇门 ──

    def pan_minute(self, option=1):
        """
        刻家奇门起盘
        option: 1=拆补, 2=置闰
        """
        args = self._args()
        gz = ganzhi.gangzhi(*args)
        gzd = f"{gz[0]}年{gz[1]}月{gz[2]}日{gz[3]}時{gz[4]}分"

        ju_str = {1: ganzhi.ju_chaibu, 2: ganzhi.ju_zhirun}.get(option)(*args)
        shunhead = ganzhi.xun_shou(gz[3])
        shunkong = ganzhi.hourkong_minutekong(*args)
        jieqi = ganzhi.jq(*args)
        zfzs = plates.zhifu_n_zhishi_ke(*args, option)

        star_result = plates.stars_minute(*args, option)
        star = star_result[0]
        door = plates.doors_minute(*args, option)
        god = plates.gods_minute(*args, option)

        return {
            "排盤方式": {1: "拆補", 2: "置閏"}.get(option),
            "干支": gzd,
            "旬首": shunhead,
            "旬空": shunkong,
            "局日": ganzhi.ju_day(*args),
            "排局": ju_str,
            "節氣": jieqi,
            "值符值使": zfzs,
            "天乙": plates.tianyi(*args, option),
            "天盤": plates.sky_plate_minute(*args, option),
            "地盤": plates.earth_plate_minute(*args),
            "門": door,
            "星": star,
            "神": god,
            "馬星": {
                "天馬": plates.moon_horse(*args),
                "丁馬": plates.din_horse(*args),
                "驛馬": plates.hour_horse(*args),
            },
            "長生運": stages.twelve_stages_minute(*args, option),
        }

    # ── 金函玉镜 (日家) ──

    def gpan(self):
        """金函玉镜日家奇门"""
        return plates.gpan(*self._args())

    # ── 综合排盘 ──

    def overall(self, option=1):
        """综合排盘: 时家 + 金函 + 刻家"""
        return {
            "金函玉鏡(日家奇門)": self.gpan(),
            "時家奇門": self.pan(option),
            "刻家奇門": self.pan_minute(option),
        }
