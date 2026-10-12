"""酒店搜索工具 — Amadeus Hotel List API"""

import json
import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings


class HotelSearchInput(BaseModel):
    """酒店搜索参数"""

    city_code: str = Field(description="城市 IATA 码，如 TYO（东京）")
    check_in: str = Field(description="入住日期 YYYY-MM-DD")
    check_out: str = Field(description="退房日期 YYYY-MM-DD")
    adults: int = Field(default=1, description="成人数量")
    radius: int = Field(default=20, description="搜索半径（km）")
    radius_unit: str = Field(default="KM")


class HotelSearchTool(BaseTool):
    """搜索目的地酒店"""

    name: str = "search_hotels"
    description: str = (
        "搜索目的地酒店，返回酒店名称、星级、区域、每晚价格、评分、设施等信息。"
        "参数示例：city_code='TYO', check_in='2026-10-01', check_out='2026-10-07', adults=2"
    )
    args_schema: type[BaseModel] = HotelSearchInput

    _access_token: str | None = None

    async def _get_token(self) -> str:
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

    async def _arun(
        self,
        city_code: str,
        check_in: str,
        check_out: str,
        adults: int = 1,
        radius: int = 20,
        radius_unit: str = "KM",
    ) -> str:
        try:
            token = await self._get_token()

            async with httpx.AsyncClient(timeout=30.0) as client:
                # 先获取城市经纬度 → 再搜酒店
                resp = await client.get(
                    "https://test.api.amadeus.com/v1/reference-data/locations/cities",
                    params={"keyword": city_code, "max": 1},
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                cities = resp.json().get("data", [])
                if not cities:
                    return json.dumps({"error": f"未找到城市: {city_code}", "candidates": []})

                geo = cities[0]["geoCode"]
                lat, lng = geo["latitude"], geo["longitude"]

                # 搜酒店
                resp2 = await client.get(
                    "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-geocode",
                    params={
                        "latitude": lat,
                        "longitude": lng,
                        "radius": radius,
                        "radiusUnit": radius_unit,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp2.raise_for_status()
                hotels_raw = resp2.json().get("data", [])

            candidates = []
            for h in hotels_raw[:20]:  # 最多 20 个
                candidates.append({
                    "id": h.get("hotelId", ""),
                    "name": h.get("name", ""),
                    "chain_code": h.get("chainCode", ""),
                    "iata_code": h.get("iataCode", ""),
                    "latitude": h.get("geoCode", {}).get("latitude"),
                    "longitude": h.get("geoCode", {}).get("longitude"),
                })

            return json.dumps({"candidates": candidates}, ensure_ascii=False)

        except httpx.HTTPError as e:
            return json.dumps({"error": f"酒店搜索失败: {str(e)}", "candidates": []})
        except Exception as e:
            return json.dumps({"error": f"未知错误: {str(e)}", "candidates": []})

    def _run(self, **kwargs) -> str:
        import asyncio
        return asyncio.run(self._arun(**kwargs))
