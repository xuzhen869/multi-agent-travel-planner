"""地理编码 — 统一城市 → 机场码/城市码映射。

历史问题：flight_agent / hotel_agent / lookup 各自维护一套映射，
且对未知城市 fallback 成 `city.upper()[:3]`（中文城市生成非法 IATA）。
本模块收敛为单一数据源：
  - `flight`：出发/到达搜索用主机场码（如上海 PVG）
  - `metro`：城市级查询用城市码（如上海 SHA，酒店按城市搜）
未知城市统一返回 None，由调用方决定是否降级，不再生成非法码。
"""

# 城市码：metropolitan area code（3 字母，用于城市级查询）
_CITY_MAP: dict[str, dict] = {
    # —— 国内 ——
    "上海": {"flight": "PVG", "metro": "SHA", "airports": ["PVG", "SHA"]},
    "北京": {"flight": "PEK", "metro": "BJS", "airports": ["PEK", "PKX"]},
    "成都": {"flight": "CTU", "metro": "CTU", "airports": ["CTU", "TFU"]},
    "重庆": {"flight": "CKG", "metro": "CKG", "airports": ["CKG"]},
    "杭州": {"flight": "HGH", "metro": "HGH", "airports": ["HGH"]},
    "西安": {"flight": "XIY", "metro": "XIY", "airports": ["XIY"]},
    "南京": {"flight": "NKG", "metro": "NKG", "airports": ["NKG"]},
    "武汉": {"flight": "WUH", "metro": "WUH", "airports": ["WUH"]},
    "广州": {"flight": "CAN", "metro": "CAN", "airports": ["CAN"]},
    "深圳": {"flight": "SZX", "metro": "SZX", "airports": ["SZX"]},
    "三亚": {"flight": "SYX", "metro": "SYX", "airports": ["SYX"]},
    "厦门": {"flight": "XMN", "metro": "XMN", "airports": ["XMN"]},
    "青岛": {"flight": "TAO", "metro": "TAO", "airports": ["TAO"]},
    "大连": {"flight": "DLC", "metro": "DLC", "airports": ["DLC"]},
    "昆明": {"flight": "KMG", "metro": "KMG", "airports": ["KMG"]},
    "丽江": {"flight": "LJG", "metro": "LJG", "airports": ["LJG"]},
    "长沙": {"flight": "CSX", "metro": "CSX", "airports": ["CSX"]},
    "苏州": {"flight": "SZV", "metro": "SZV", "airports": ["SZV"]},
    "桂林": {"flight": "KWL", "metro": "KWL", "airports": ["KWL"]},
    "哈尔滨": {"flight": "HRB", "metro": "HRB", "airports": ["HRB"]},
    "天津": {"flight": "TSN", "metro": "TSN", "airports": ["TSN"]},
    # —— 境外 ——
    "东京": {"flight": "NRT", "metro": "TYO", "airports": ["NRT", "HND"]},
    "东京": {"flight": "NRT", "metro": "TYO", "airports": ["NRT", "HND"]},
    "大阪": {"flight": "KIX", "metro": "OSA", "airports": ["KIX", "ITM"]},
    "京都": {"flight": "KIX", "metro": "UKY", "airports": ["KIX"]},  # 邻近大阪，走 KIX
    "首尔": {"flight": "ICN", "metro": "SEL", "airports": ["ICN", "GMP"]},
    "曼谷": {"flight": "BKK", "metro": "BKK", "airports": ["BKK", "DMK"]},
    "新加坡": {"flight": "SIN", "metro": "SIN", "airports": ["SIN"]},
    "香港": {"flight": "HKG", "metro": "HKG", "airports": ["HKG"]},
    "台北": {"flight": "TPE", "metro": "TPE", "airports": ["TPE", "TSA"]},
    "伦敦": {"flight": "LHR", "metro": "LON", "airports": ["LHR", "LGW"]},
    "巴黎": {"flight": "CDG", "metro": "PAR", "airports": ["CDG", "ORY"]},
    "纽约": {"flight": "JFK", "metro": "NYC", "airports": ["JFK", "EWR", "LGA"]},
    "洛杉矶": {"flight": "LAX", "metro": "LAX", "airports": ["LAX"]},
    "悉尼": {"flight": "SYD", "metro": "SYD", "airports": ["SYD"]},
    "迪拜": {"flight": "DXB", "metro": "DXB", "airports": ["DXB"]},
    "巴厘岛": {"flight": "DPS", "metro": "DPS", "airports": ["DPS"]},
    "普吉岛": {"flight": "HKT", "metro": "HKT", "airports": ["HKT"]},
    "清迈": {"flight": "CNX", "metro": "CNX", "airports": ["CNX"]},
    "札幌": {"flight": "CTS", "metro": "SPK", "airports": ["CTS"]},
    "福冈": {"flight": "FUK", "metro": "FUK", "airports": ["FUK"]},
}


def city_to_flight_iata(city: str) -> str | None:
    """城市名 → 主机场 IATA 码（出发/到达、航班搜索）；未知返回 None"""
    info = _CITY_MAP.get(city)
    return info["flight"] if info else None


def city_to_metro_code(city: str) -> str | None:
    """城市名 → 城市码（酒店等城市级查询）；未知返回 None"""
    info = _CITY_MAP.get(city)
    return info["metro"] if info else None


def city_info(city: str) -> dict | None:
    """城市完整信息（含机场列表）"""
    return _CITY_MAP.get(city)


def search_cities(keyword: str) -> list[dict]:
    """城市搜索（供 lookup 端点）"""
    results = []
    for name, info in _CITY_MAP.items():
        if keyword.lower() in name.lower():
            results.append({"name": name, "iata": info["metro"], "airports": info["airports"]})
    return results


def search_iata(keyword: str) -> list[dict]:
    """机场/IATA 搜索（供 lookup 端点）"""
    results = []
    for name, info in _CITY_MAP.items():
        if keyword.lower() in name.lower() or keyword.upper() in info["airports"]:
            results.append({"city": name, "iata_code": info["metro"], "airports": info["airports"]})
    return results
