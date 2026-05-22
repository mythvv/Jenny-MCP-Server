"""
紫微斗数数据表

纯数据，零函数。
"""

# ── 天干地支 ──
GAN_MAP = {
    "jiaHeavenly": "甲", "yiHeavenly": "乙", "bingHeavenly": "丙",
    "dingHeavenly": "丁", "wuHeavenly": "戊", "jiHeavenly": "己",
    "gengHeavenly": "庚", "xinHeavenly": "辛", "renHeavenly": "壬",
    "guiHeavenly": "癸",
}

ZHI_MAP = {
    "ziEarthly": "子", "chouEarthly": "丑", "yinEarthly": "寅",
    "maoEarthly": "卯", "chenEarthly": "辰", "siEarthly": "巳",
    "wuEarthly": "午", "weiEarthly": "未", "shenEarthly": "申",
    "youEarthly": "酉", "xuEarthly": "戌", "haiEarthly": "亥",
}

# ── 十二宫 ──
PALACE_NAMES = [
    "命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
    "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫",
]

# ── 时辰 → 小时范围 ──
HOUR_RANGES = [
    (23, 1),   # 子
    (1, 3),    # 丑
    (3, 5),    # 寅
    (5, 7),    # 卯
    (7, 9),    # 辰
    (9, 11),   # 巳
    (11, 13),  # 午
    (13, 15),  # 未
    (15, 17),  # 申
    (17, 19),  # 酉
    (19, 21),  # 戌
    (21, 23),  # 亥
]

# ── 星曜中英映射 ──
STAR_NAME_MAP = {
    # 十四主星
    "ziweiMaj": "紫微", "tianjiMaj": "天机", "taiyangMaj": "太阳",
    "wuquMaj": "武曲", "tiantongMaj": "天同", "lianzhenMaj": "廉贞",
    "tianfuMaj": "天府", "taiyinMaj": "太阴", "tanlangMaj": "贪狼",
    "jumenMaj": "巨门", "tianxiangMaj": "天相", "tianliangMaj": "天梁",
    "qishaMaj": "七杀", "pojunMaj": "破军",
    # 辅星
    "zuofuMin": "左辅", "youbiMin": "右弼", "wenchangMin": "文昌",
    "wenquMin": "文曲", "tiankuiMin": "天魁", "tianyueMin": "天钺",
    "lucunMin": "禄存", "qingyangMin": "擎羊", "tuoluoMin": "陀罗",
    "huoxingMin": "火星", "lingxingMin": "铃星", "dikongMin": "地空",
    "dijieMin": "地劫", "tianmaMin": "天马",
}

# ── 星曜亮度 ──
BRIGHTNESS_MAP = {
    "miao": "庙", "wang": "旺", "de": "得", "li": "利",
    "ping": "平", "bu": "不", "xian": "陷",
}

# ── 杂曜/神煞（adjective_stars）中英映射 ──
ADJECTIVE_STAR_MAP = {
    "tianchu": "天厨", "tianyue": "天钺", "feilian": "飞廉",
    "tianxi": "天喜", "xianchi": "咸池", "santai": "三台",
    "tiande": "天德", "tianshang": "天伤", "tianyao": "天妖",
    "fengge": "封诰", "tiancai": "天才", "guasu": "寡宿",
    "nianjie": "年解", "posui": "破碎", "tianshi": "天使",
    "tiangui": "天贵", "tianshou": "天寿", "tianfuAdj": "天福",
    "jielu": "截路", "tiankong": "天空", "kongwang": "空亡",
    "guchen": "孤辰", "yinsha": "阴煞", "hongluan": "红鸾",
    "fenggao": "封诰", "jieshen": "解神", "enguang": "恩光",
    "longchi": "龙池", "huagai": "华盖", "xunkong": "旬空",
    "bazuo": "八座", "tianwu": "天巫", "tianguan": "天官",
    "yuede": "月德", "tianxing": "天刑", "tianku": "天哭",
    "tianxu": "天虚", "taifu": "台辅",
    "tianma": "天马", "tiankuang": "天狂",
    "tianyu": "天雨", "tianlang": "天狼",
    "jieyj": "劫煞",
}

# ── 四化 ──
MUTAGEN_MAP = {
    "lu": "化禄", "quan": "化权", "ke": "化科", "ji": "化忌",
}

# ── 五行局 ──
FIVE_ELEMENTS_MAP = {
    "water2": "水二局", "wood3": "木三局", "metal4": "金四局",
    "earth5": "土五局", "fire6": "火六局",
}

# ── 十二长生 ──
CHANGSHENG_12 = [
    "长生", "沐浴", "冠带", "临官", "帝旺", "衰",
    "病", "死", "墓", "绝", "胎", "养",
]
