"""百度地图 Web 服务 API 适配层 — 天气 / 地理编码 / POI 检索 / 路线规划

覆盖 Google Places / OpenWeather 的国内数据源。认证支持两种模式
（在百度地图开放平台 lbsyun.baidu.com 申请 AK 时选择）：
  - IP 白名单模式：只需配置 BAIDU_MAP_AK
  - SN 校验模式：配置 BAIDU_MAP_AK + BAIDU_MAP_SK（自动生成 sn 签名）

所有接口在未配置 AK 或调用失败时返回可解析的空结果，
配合各 Agent 的规则兜底保证流程不中断。
注意：百度天气/POI 主要覆盖国内，境外城市（无行政区划编码）自动降级为空。
"""

import hashlib
import json
import logging
from typing import Any

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from urllib.parse import urlencode, quote

from app.config import settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.map.baidu.com"

# 国内主要城市 → 行政区划编码（百度天气 district_id；境外城市不在表中则天气降级为空）
# 注意：直辖市需用区级编码（市级编码百度不识别），地级市用市级编码
_DISTRICT_MAP: dict[str, str] = {
    "北京": "110101", "上海": "310101", "天津": "120101", "重庆": "500103",
    "广州": "440100", "深圳": "440300",
    "成都": "510100", "杭州": "330100", "西安": "610100",
    "南京": "320100", "武汉": "420100", "三亚": "460200", "厦门": "350200",
    "青岛": "370200", "大连": "210200", "昆明": "530100", "丽江": "530700",
    "长沙": "430100", "苏州": "320500", "桂林": "450300",
    "哈尔滨": "230100", "乌鲁木齐": "650100", "拉萨": "540100", "郑州": "410100",
    "济南": "370100", "福州": "350100", "海口": "460100", "沈阳": "210100",
    "南宁": "450100", "贵阳": "520100", "兰州": "620100", "呼和浩特": "150100",
    "石家庄": "130100", "合肥": "340100", "南昌": "360100", "太原": "140100",
    "长春": "220100", "西宁": "630100", "银川": "640100", "张家界": "430800",
}


def city_to_district_id(city: str) -> str | None:
    """城市名 → 百度行政区划编码（用于天气查询）；未知城市返回 None"""
    return _DISTRICT_MAP.get(city)


def _calc_sn(path: str, params: dict, sk: str) -> str:
    """计算百度 SN 校验签名（AK+SK 模式）"""
    querystring = urlencode(sorted(params.items()))
    raw = quote(f"{path}?{querystring}{sk}", safe="/:=&?#+!$,;'@()*[]")
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


async def _baidu_get(path: str, params: dict) -> dict:
    """调用百度地图 Web API；未配置 AK 时返回错误结构"""
    if not settings.BAIDU_MAP_AK:
        return {"status": -1, "message": "BAIDU_MAP_AK 未配置"}
    params = {**params, "ak": settings.BAIDU_MAP_AK, "output": "json"}
    if settings.BAIDU_MAP_SK:
        params["sn"] = _calc_sn(path, params, settings.BAIDU_MAP_SK)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{_API_BASE}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("百度 API 调用失败 %s: %s", path, e)
        return {"status": -1, "message": str(e)}


# ——— 地理编码 ———


async def geocode(address: str, city: str | None = None) -> dict | None:
    """地址 → 经纬度（bd09ll）；失败返回 None"""
    params: dict = {"address": address}
    if city:
        params["city"] = city
    data = await _baidu_get("/geocoding/v3/", params)
    if data.get("status") != 0:
        return None
    result = data.get("result") or {}
    loc = result.get("location") or {}
    if not loc:
        return None
    return {"lat": loc.get("lat"), "lng": loc.get("lng"), "level": result.get("level")}


# ——— 地点检索（POI） ———


async def place_search(
    query: str, region: str | None = None, max_results: int = 10
) -> dict:
    """按关键词检索 POI；返回与 POISearchTool 兼容的 poi_list 结构"""
    if not settings.BAIDU_MAP_AK:
        return {"poi_list": [], "error": "BAIDU_MAP_AK 未配置"}
    params: dict = {
        "query": query,
        "output": "json",
        "scope": "2",
        "page_size": min(max(max_results, 1), 20),
    }
    if region:
        params["region"] = region
    data = await _baidu_get("/place/v2/search", params)
    if data.get("status") != 0:
        return {"poi_list": [], "error": data.get("message")}

    results = []
    for poi in (data.get("results") or [])[:max_results]:
        loc = poi.get("location") or {}
        detail = poi.get("detail_info") or {}
        results.append({
            "id": poi.get("uid", ""),
            "name": poi.get("name", ""),
            "formatted_address": poi.get("address", ""),
            "rating": detail.get("rating"),
            "user_ratings_total": None,
            "types": [],
            "price_level": None,
            "geometry": {"lat": loc.get("lat"), "lng": loc.get("lng")},
            "opening_hours": None,
        })
    return {"poi_list": results}


# ——— 天气 ———


async def weather(city: str, date: str | None = None) -> dict:
    """查询城市天气（百度，国内城市）；返回与 WeatherTool 兼容的 forecast 结构"""
    if not settings.BAIDU_MAP_AK:
        return {"city": city, "forecast": [], "error": "BAIDU_MAP_AK 未配置"}
    district_id = city_to_district_id(city)
    if not district_id:
        # 境外/未知城市：百度天气无行政区划编码，降级为空
        return {"city": city, "forecast": [], "error": "该城市不支持百度天气（无行政区划编码）"}

    data = await _baidu_get("/weather/v1/", {"district_id": district_id, "data_type": "all"})
    if data.get("status") != 0:
        return {"city": city, "forecast": [], "error": data.get("message")}

    result = data.get("result") or {}
    now = result.get("now") or {}
    humidity = now.get("rh")

    forecast = []
    for f in result.get("forecasts") or []:
        high, low = f.get("high"), f.get("low")
        try:
            high_v, low_v = float(high), float(low)
            avg = round((high_v + low_v) / 2, 1)
        except (TypeError, ValueError):
            high_v = low_v = avg = None
        forecast.append({
            "date": f.get("date", ""),
            "temp_min": low_v,
            "temp_max": high_v,
            "temp_avg": avg,
            "main_weather": f.get("text_day") or f.get("text_night", ""),
            "humidity_avg": humidity,
        })

    if date:
        forecast = [f for f in forecast if f["date"] == date]
    return {"city": city, "forecast": forecast}


# ——— 路线规划 ———


async def direction(origin: str, destination: str, mode: str = "walking") -> dict:
    """两点间路线规划（origin/destination 格式：'lat,lng'），mode: walking|driving|riding|transit"""
    if not settings.BAIDU_MAP_AK:
        return {"error": "BAIDU_MAP_AK 未配置", "routes": []}
    params = {"origin": origin, "destination": destination}
    data = await _baidu_get(f"/direction/v2/{mode}", params)
    if data.get("status") != 0:
        return {"error": data.get("message"), "routes": []}

    routes = []
    for r in (data.get("result") or {}).get("routes") or []:
        routes.append({
            "distance": r.get("distance", {}),
            "duration": r.get("duration", {}),
            "steps": (r.get("steps") or [])[:10],
        })
    return {"routes": routes}


# ——— LangChain 工具类（供 Agent / lookup 使用） ———


class BaiduGeocodeInput(BaseModel):
    address: str = Field(description="结构化地址，如 '上海市黄浦区'")
    city: str | None = Field(default=None, description="城市名，用于过滤同名地址")


class BaiduGeocodeTool(BaseTool):
    """百度地理编码 — 地址转经纬度"""

    name: str = "baidu_geocode"
    description: str = "地址转经纬度坐标。参数示例：address='上海 外滩', city='上海'"
    args_schema: type[BaseModel] = BaiduGeocodeInput

    async def _arun(self, address: str, city: str | None = None) -> str:
        result = await geocode(address, city)
        if result is None:
            return json.dumps({"error": "地理编码失败"}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False)

    def _run(self, **kwargs: Any) -> str:
        import asyncio
        return asyncio.run(self._arun(**kwargs))


class BaiduDirectionInput(BaseModel):
    origin: str = Field(description="起点经纬度，格式 '纬度,经度'")
    destination: str = Field(description="终点经纬度，格式 '纬度,经度'")
    mode: str = Field(default="walking", description="walking|driving|riding|transit")


class BaiduDirectionTool(BaseTool):
    """百度路线规划 — 两点间步行/驾车/公交路线"""

    name: str = "baidu_direction"
    description: str = "两点间路线规划，返回距离、耗时与分步导航。参数示例：origin='31.23,121.47', destination='31.25,121.50', mode='walking'"
    args_schema: type[BaseModel] = BaiduDirectionInput

    async def _arun(self, origin: str, destination: str, mode: str = "walking") -> str:
        result = await direction(origin, destination, mode)
        return json.dumps(result, ensure_ascii=False)

    def _run(self, **kwargs: Any) -> str:
        import asyncio
        return asyncio.run(self._arun(**kwargs))
