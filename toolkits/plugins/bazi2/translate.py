"""
八字 — 数据查询层
"""

from . import tables as T


def element_cn(gan_or_zhi: str) -> str:
    """天干或地支 → 中文五行"""
    return T.WUXING_GAN.get(gan_or_zhi, T.WUXING_ZHI.get(gan_or_zhi, ""))


def yinyang(gan: str) -> str:
    """天干 → 阴阳"""
    return T.YIN_YANG.get(gan, "")


def wuxing_relation(element1: str, element2: str) -> str:
    """element1 对 element2 的五行关系"""
    if element1 == element2:
        return "比助（同五行）"
    if T.SHENG_MAP.get(element1) == element2:
        return "泄气（我生）"
    if T.KE_MAP.get(element1) == element2:
        return "耗气（我克）"
    if T.BEI_KE_MAP.get(element1) == element2:
        return "受克（克我）"
    if T.SHENG_MAP.get(element2) == element1:
        return "生助（生我）"
    return ""
