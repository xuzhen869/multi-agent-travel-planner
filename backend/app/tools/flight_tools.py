"""航班搜索工具 — Amadeus Flight Offers Search API

封装为 LangChain BaseTool，供 FlightAgent 调用。
"""

import json
import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings


class FlightSearchInput(BaseModel):
    """航班搜索参数"""

    origin: str = Field(description="出发城市 IATA 码，如 PVG（上海浦东）")
    destination: str = Field(description="目的地城市 IATA 码，如 NRT（东京成田）")
    departure_date: str = Field(description="出发日期 YYYY-MM-DD")
    return_date: str = Field(description="返程日期 YYYY-MM-DD")
    adults: int = Field(default=1, description="成人数量")


class FlightSearchTool(BaseTool):
    """搜索往返航班"""

    name: str = "search_flights"
    description: str = (
        "搜索往返航班，返回航班号、出发/到达时间、航司、价格、经停次数、飞行时长等信息。"
        "参数示例：origin='PVG', destination='NRT', departure_date='2026-10-01', "
        "return_date='2026-10-07', adults=2"
    )
    args_schema: type[BaseModel] = FlightSearchInput

    # ——— Amadeus 认证 ———

    _access_token: str | None = None

    async def _get_token(self) -> str:
        """获取 Amadeus API access token（带缓存）"""
        if self._access_token:
            return self._access_token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://test.api.amadeus.com/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.AMADEUS_API_KEY,
                    "client_secret": settings.AMADEUS_API_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            return self._access_token

    # ——— 核心逻辑 ———

    async def _arun(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        adults: int = 1,
    ) -> str:
        """异步执行航班搜索"""
        try:
            token = await self._get_token()

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://test.api.amadeus.com/v2/shopping/flight-offers",
                    params={
                        "originLocationCode": origin,
                        "destinationLocationCode": destination,
                        "departureDate": departure_date,
                        "returnDate": return_date,
                        "adults": adults,
                        "currencyCode": "CNY",
                        "max": 10,  # 最多 10 个结果
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                raw = resp.json()

            # 精简响应：只保留关键字段
            candidates = []
            for offer in raw.get("data", []):
                itinerary = offer.get("itineraries", [])
                outbound = None
                inbound = None

                for seg in itinerary:
                    segments = seg.get("segments", [])
                    if not segments:
                        continue
                    first_seg = segments[0]
                    last_seg = segments[-1]
                    flight_info = {
                        "departure": first_seg["departure"]["at"],
                        "arrival": last_seg["arrival"]["at"],
                        "stops": len(segments) - 1,
                        "duration": seg.get("duration", ""),
                        "airline": first_seg.get("carrierCode", ""),
                    }
                    if outbound is None:
                        outbound = flight_info
                    else:
                        inbound = flight_info

                price = float(offer.get("price", {}).get("grandTotal", 0))

                candidates.append({
                    "id": offer.get("id", ""),
                    "outbound": outbound,
                    "return": inbound,
                    "total_price": price,
                    "currency": "CNY",
                })

            return json.dumps({"candidates": candidates}, ensure_ascii=False)

        except httpx.HTTPError as e:
            return json.dumps({"error": f"航班搜索失败: {str(e)}", "candidates": []})
        except Exception as e:
            return json.dumps({"error": f"未知错误: {str(e)}", "candidates": []})

    def _run(self, **kwargs) -> str:
        """同步入口（LangChain 要求，内部转异步）"""
        import asyncio
        return asyncio.run(self._arun(**kwargs))
