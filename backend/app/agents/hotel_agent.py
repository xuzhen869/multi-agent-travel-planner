"""酒店搜索 Agent"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings
from app.tools.hotel_tools import HotelSearchTool

logger = logging.getLogger(__name__)

HOTEL_SYSTEM_PROMPT = """你是一个酒店推荐专家。根据搜索结果和用户偏好：

1. 按星级、位置、估算价格筛选
2. 计算综合评分（0-1）
3. 推荐 Top 5 酒店

输出严格 JSON：
{
  "candidates": [
    {
      "id": "HT-001",
      "name": "新宿京王广场酒店",
      "star": 4,
      "area": "新宿",
      "price_per_night_estimate": 800,
      "total_price_estimate": 5600,
      "rating": 4.3,
      "score": 0.88,
      "recommendation_note": "位置绝佳，性价比高"
    }
  ]
}"""


class HotelAgent(BaseAgent):
    """酒店搜索 Agent"""

    name = "hotel_agent"
    description = "搜索酒店并按偏好排序"

    def __init__(self):
        self.llm = get_llm(temperature=0.3, max_tokens=4096)
        self.tool = HotelSearchTool()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")
        dest_city = state.get("destination", "")
        strategy = state.get("current_strategy", {})
        star_override = strategy.get("strategy", {}).get("hotel_star_override",
            state.get("preferences", {}).get("hotel_star", 4))

        try:
            # 城市 → IATA 码（未知城市降级，不生成非法码）
            iata = await self._city_to_iata(dest_city)
            if not iata:
                logger.warning("[%s] 未知城市 IATA，跳过酒店搜索：%s", trip_id, dest_city)
                return {"hotel_candidates": []}

            raw_result = await self.tool._arun(
                city_code=iata,
                check_in=state.get("start_date", ""),
                check_out=state.get("end_date", ""),
                adults=len(state.get("travelers", [{"age": 30}])),
            )

            tool_data = json.loads(raw_result)
            candidates_raw = tool_data.get("candidates", [])

            if not candidates_raw:
                logger.warning("[%s] 未找到酒店", trip_id)
                return {"hotel_candidates": []}

            # LLM 推理排序
            days = self._count_days(state.get("start_date", ""), state.get("end_date", ""))
            prompt = (
                f"偏好星级：{star_override} 星\n目的地：{dest_city}\n入住天数：{days} 晚\n"
                f"原始酒店数据：{json.dumps(candidates_raw[:15], ensure_ascii=False)}"
            )

            messages = [
                SystemMessage(content=HOTEL_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            parsed = self._parse_json(content)
            candidates = parsed.get("candidates", []) if parsed else []

            logger.info("[%s] HotelAgent 完成：%d 个候选酒店", trip_id, len(candidates))
            return {"hotel_candidates": candidates}

        except Exception as e:
            logger.exception("[%s] HotelAgent 失败: %s", trip_id, e)
            return {"hotel_candidates": []}

    async def _city_to_iata(self, city: str) -> str | None:
        """城市名 → 城市码（酒店按城市级查询；未知返回 None，交由调用方降级）"""
        from app.core.geocode import city_to_metro_code

        return city_to_metro_code(city)

    def _count_days(self, start: str, end: str) -> int:
        try:
            from datetime import datetime
            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(end, "%Y-%m-%d")
            return max(1, (e - s).days)
        except Exception:
            return 5

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
