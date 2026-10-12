"""POI 搜索 Agent — 景点和餐厅推荐（含天气上下文）"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings
from app.tools.poi_tools import POISearchTool
from app.tools.weather_tools import WeatherTool

logger = logging.getLogger(__name__)

POI_SYSTEM_PROMPT = """你是一个旅行景点/餐厅推荐专家。根据搜索结果为用户整理 POI 清单。

对于景点，补充关键信息（从名称和类型推理）：
- category: 历史文化/自然景观/购物/艺术/娱乐/美食
- duration_min: 建议游览时长
- estimated_price: 预估门票价格（CNY）
- tips: 实用小贴士

对于餐厅，补充：
- cuisine: 菜系类型
- price_level: 人均消费（¥/¥¥/¥¥¥）
- must_try: 推荐菜品

输出严格 JSON：
{
  "attractions": [
    {"id": "POI-001", "name": "浅草寺", "category": "历史文化", "rating": 4.5,
     "duration_min": 90, "estimated_price": 0, "opening_hours": "06:00-17:00",
     "location": {"lat": 35.7148, "lng": 139.7967}, "tips": "清晨人少"}
  ],
  "restaurants": [
    {"id": "RST-001", "name": "一兰拉面", "cuisine": "日式拉面", "price_level": "¥¥",
     "rating": 4.3, "opening_hours": "11:00-23:00", "must_try": "经典豚骨拉面",
     "location": {"lat": 35.6938, "lng": 139.7036}}
  ]
}"""


class POIAgent(BaseAgent):
    """POI 搜索 Agent"""

    name = "poi_agent"
    description = "搜索景点和餐厅并分类"

    def __init__(self):
        self.llm = get_llm(temperature=0.3, max_tokens=8192)
        self.tool = POISearchTool()
        self.weather_tool = WeatherTool()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")
        destination = state.get("destination", "")
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        preferences = state.get("preferences", {})
        interests = preferences.get("interests", ["景点", "美食"])

        try:
            # 并行搜索景点、餐厅、天气
            import asyncio

            attr_task = self.tool._arun(
                query=f"{destination} 必去景点",
                region=destination,
                poi_type="tourist_attraction",
                max_results=15,
            )
            rest_task = self.tool._arun(
                query=f"{destination} 推荐餐厅",
                region=destination,
                poi_type="restaurant",
                max_results=15,
            )
            # 天气为近期参考（短期预报无法覆盖远期行程日期），不按行程日期过滤
            weather_task = self.weather_tool._arun(city=destination)

            attr_raw, rest_raw, weather_raw = await asyncio.gather(
                attr_task, rest_task, weather_task, return_exceptions=True
            )

            attr_data = json.loads(attr_raw) if not isinstance(attr_raw, Exception) else {"poi_list": []}
            rest_data = json.loads(rest_raw) if not isinstance(rest_raw, Exception) else {"poi_list": []}
            weather_data = json.loads(weather_raw) if not isinstance(weather_raw, Exception) else {"forecast": []}

            all_poi = attr_data.get("poi_list", []) + rest_data.get("poi_list", [])

            if not all_poi:
                logger.warning("[%s] 未找到 POI", trip_id)
                return {"poi_data": {"attractions": [], "restaurants": [], "weather": weather_data.get("forecast", [])}}

            # LLM 分类和增强（附带天气信息）
            prompt = (
                f"目的地：{destination}\n用户兴趣：{interests}\n"
                f"天气预报：{json.dumps(weather_data.get('forecast', []), ensure_ascii=False)}\n"
                f"原始 POI 数据：{json.dumps(all_poi[:30], ensure_ascii=False)}"
            )

            messages = [
                SystemMessage(content=POI_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            parsed = self._parse_json(content)
            poi_data = parsed if parsed else {"attractions": [], "restaurants": []}
            # 附带天气
            poi_data["weather"] = weather_data.get("forecast", [])

            logger.info("[%s] POIAgent 完成：%d 景点, %d 餐厅, %d 天天气",
                        trip_id,
                        len(poi_data.get("attractions", [])),
                        len(poi_data.get("restaurants", [])),
                        len(poi_data.get("weather", [])))
            return {"poi_data": poi_data}

        except Exception as e:
            logger.exception("[%s] POIAgent 失败: %s", trip_id, e)
            return {"poi_data": {"attractions": [], "restaurants": []}}

    def _parse_json(self, text: str) -> dict | None:
        import re
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None
