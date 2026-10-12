"""辅助查询 API——城市搜索、IATA 码查询、汇率"""

import json
from fastapi import APIRouter, Query

from app.core.geocode import search_cities as _search_cities
from app.core.geocode import search_iata as _search_iata

router = APIRouter(prefix="/api/lookup", tags=["辅助查询"])


@router.get("/cities")
async def search_cities(q: str = Query(min_length=1, description="城市关键词")):
    """城市搜索（含 IATA 码）"""
    return {"cities": _search_cities(q)}


@router.get("/iata")
async def search_iata(keyword: str = Query(min_length=1)):
    """机场/IATA 码查询"""
    return {"results": _search_iata(keyword)}


@router.get("/exchange")
async def exchange_rate(
    from_currency: str = Query(default="CNY", alias="from", max_length=3),
    to: str = Query(default="JPY", max_length=3),
    amount: float = Query(default=1000, ge=0),
):
    """汇率换算（优先使用实时 API，失败时回退静态数据）"""
    try:
        from app.tools.currency_tools import CurrencyTool
        tool = CurrencyTool()
        result_json = await tool._arun(
            from_currency=from_currency, to_currency=to, amount=amount
        )
        result = json.loads(result_json)
        if "error" not in result:
            return result
    except Exception:
        pass

    # 回退静态汇率
    _RATES: dict[str, float] = {
        "CNY": 1.0, "JPY": 20.5, "USD": 0.14, "EUR": 0.13,
        "KRW": 187.0, "THB": 5.1, "SGD": 0.19, "HKD": 1.1,
        "TWD": 4.5, "GBP": 0.11, "AUD": 0.21, "AED": 0.51,
    }

    from_rate = _RATES.get(from_currency.upper())
    to_rate = _RATES.get(to.upper())

    if from_rate is None or to_rate is None:
        return {"error": "不支持的货币", "supported": list(_RATES.keys())}

    converted = amount * (to_rate / from_rate)
    return {
        "from": from_currency.upper(),
        "to": to.upper(),
        "amount": amount,
        "result": round(converted, 2),
        "rate": round(to_rate / from_rate, 6),
    }


@router.get("/geocode")
async def geocode(
    address: str = Query(min_length=1, description="结构化地址，如 '上海 外滩'"),
    city: str | None = Query(default=None, description="城市名，用于过滤同名地址"),
):
    """地址 → 经纬度（百度地图地理编码）"""
    from app.tools.baidu_tools import geocode as _geocode

    result = await _geocode(address, city)
    if result is None:
        return {"error": "地理编码失败（可能未配置百度 AK 或地址无效）"}
    return result


@router.get("/direction")
async def direction(
    origin: str = Query(min_length=1, description="起点经纬度，格式 '纬度,经度'"),
    destination: str = Query(min_length=1, description="终点经纬度，格式 '纬度,经度'"),
    mode: str = Query(default="walking", description="walking|driving|riding|transit"),
):
    """两点间路线规划（百度地图）"""
    from app.tools.baidu_tools import direction as _direction

    return await _direction(origin, destination, mode)
