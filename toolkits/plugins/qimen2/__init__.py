"""
qimen2 — 奇门遁甲重构版

库模块: qimen.py, plates.py, ganzhi.py, stages.py, tables.py
工具包入口: Qimen2Toolkit
"""

from toolkits.base import BaseToolkit
from .qimen import Qimen

__all__ = ["Qimen", "Qimen2Toolkit"]

PALACE_MAP = {
    "坎": "一", "坤": "二", "震": "三", "巽": "四",
    "中": "五", "乾": "六", "兌": "七", "艮": "八", "離": "九",
}

METHOD_MAP = {"拆补": 1, "置闰": 2}

_NOT_APPLICABLE = "日家奇门不适用此字段"


def _format_pan(result: dict) -> dict:
    is_gpan = result.get("排盤方式") == "金函玉鏡"
    formatted = {
        "method": result.get("排盤方式", "") or result.get("局", ""),
        "ganzhi": result.get("干支", ""),
        "xun_shou": result.get("旬首", ""),
        "xun_kong": result.get("旬空") or {},
        "ju": result.get("排局", "") or result.get("局", ""),
        "jieqi": result.get("節氣", ""),
        "zhifu_zhishi": result.get("值符值使") or ({"_note": _NOT_APPLICABLE} if is_gpan else {}),
        "tianyi": result.get("天乙", "") or "",
        "sky_plate": result.get("天盤") or ({"_note": _NOT_APPLICABLE} if is_gpan else {}),
        "earth_plate": result.get("地盤") or ({"_note": _NOT_APPLICABLE} if is_gpan else {}),
        "doors": result.get("門") or {},
        "stars": result.get("星") or {},
        "gods": result.get("神") or {},
        "horse_stars": result.get("馬星") or {},
        "twelve_stages": result.get("長生運") or ({"_note": _NOT_APPLICABLE} if is_gpan else {}),
    }
    if "鶴神" in result:
        formatted["crane_god"] = result["鶴神"] or ""
    return formatted


class Qimen2Toolkit(BaseToolkit):
    """Qimen2 奇门遁甲工具包（重构版，无 kinqimen 依赖）"""

    name = "qimen2"
    description = "奇门遁甲工具包(重构版) - 时家奇门/刻家奇门/金函玉镜/综合排盘"

    def __init__(self, ctx: dict = None):
        super().__init__()

    def get_config_schema(self) -> dict:
        return {}

    def get_tools(self):
        return [
            (self.qimen2_pan, "qimen2_pan",
             "时家奇门排盘（拆补/置闰）。返回九宫格天盘/地盘/八门/九星/八神等完整信息。",
             [("year", "int", None, "年份"),
              ("month", "int", None, "月份，1-12"),
              ("day", "int", None, "日期，1-31"),
              ("hour", "int", None, "小时（24小时制）"),
              ("minute", "int", None, "分钟"),
              ("method", "str", "拆补", "排盘方式：拆补 或 置闰")]),
            (self.qimen2_minute, "qimen2_minute",
             "刻家奇门排盘（分钟精度），适合需要更精确时间定位的场景。",
             [("year", "int", None, "年份"),
              ("month", "int", None, "月份，1-12"),
              ("day", "int", None, "日期，1-31"),
              ("hour", "int", None, "小时（24小时制）"),
              ("minute", "int", None, "分钟"),
              ("method", "str", "拆补", "排盘方式：拆补 或 置闰")]),
            (self.qimen2_gpan, "qimen2_gpan",
             "金函玉镜日家奇门，返回局数/九星/八门/八神/鹤神等日家特有信息。",
             [("year", "int", None, "年份"),
              ("month", "int", None, "月份，1-12"),
              ("day", "int", None, "日期，1-31"),
              ("hour", "int", None, "小时（24小时制）"),
              ("minute", "int", None, "分钟")]),
            (self.qimen2_overall, "qimen2_overall",
             "综合排盘（时家+金函+刻家），一次返回三种排盘结果。",
             [("year", "int", None, "年份"),
              ("month", "int", None, "月份，1-12"),
              ("day", "int", None, "日期，1-31"),
              ("hour", "int", None, "小时（24小时制）"),
              ("minute", "int", None, "分钟"),
              ("method", "str", "拆补", "排盘方式：拆补 或 置闰")]),
        ]

    def _get_qm(self, year, month, day, hour, minute):
        return Qimen(int(year), int(month), int(day), int(hour), int(minute))

    async def qimen2_pan(self, year: int, month: int, day: int,
                         hour: int, minute: int, method: str = "拆补") -> dict:
        try:
            opt = METHOD_MAP.get(method, 1)
            q = self._get_qm(year, month, day, hour, minute)
            result = q.pan(opt)
            if isinstance(result, str):
                return {"error": result}
            return _format_pan(result)
        except Exception as e:
            return {"error": f"排盘失败: {e}"}

    async def qimen2_minute(self, year, month, day, hour, minute,
                            method: str = "拆补") -> dict:
        try:
            opt = METHOD_MAP.get(method, 1)
            q = self._get_qm(year, month, day, hour, minute)
            result = q.pan_minute(opt)
            if isinstance(result, str):
                return {"error": result}
            return _format_pan(result)
        except Exception as e:
            return {"error": f"排盘失败: {e}"}

    async def qimen2_gpan(self, year, month, day, hour, minute) -> dict:
        try:
            q = self._get_qm(year, month, day, hour, minute)
            result = q.gpan()
            if isinstance(result, str):
                return {"error": result}
            return _format_pan(result)
        except Exception as e:
            return {"error": f"排盘失败: {e}"}

    async def qimen2_overall(self, year, month, day, hour, minute,
                             method: str = "拆补") -> dict:
        try:
            opt = METHOD_MAP.get(method, 1)
            q = self._get_qm(year, month, day, hour, minute)
            result = q.overall(opt)
            if isinstance(result, str):
                return {"error": result}
            formatted = {}
            for key, val in result.items():
                if isinstance(val, dict):
                    try:
                        formatted[key] = _format_pan(val)
                    except Exception:
                        formatted[key] = val
                else:
                    formatted[key] = val
            return formatted
        except Exception as e:
            return {"error": f"排盘失败: {e}"}
