"""航班搜索 Agent — 调用 FlightSearchTool + LLM 排序推理"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings
from app.tools.flight_tools import FlightSearchTool

logger = logging.getLogger(__name__)

FLIGHT_SYSTEM_PROMPT = """你是一个航班搜索专家。根据搜索结果和用户偏好：

1. 筛选合适的航班
2. 按用户偏好排序（价格优先/时间优先/平衡）
3. 为每个候选计算综合评分（0-1）

输出严格 JSON：
{
  "candidates": [
    {
      "id": "FL-001",
      "flight_no": "CA929",
      "outbound": {"departure": "...", "arrival": "...", "airline": "..."},
      "return": {"departure": "...", "arrival": "...", "airline": "..."},
      "total_price": 6300,
      "stops": 0,
      "score": 0.92,
      "recommendation_note": "直飞最快，价格合理"
    }
  ]
}"""


class FlightAgent(BaseAgent):
    """航班搜索 Agent"""

    name = "flight_agent"
    description = "搜索航班并按偏好排序"

    def __init__(self):
        self.llm = get_llm(temperature=0.3, max_tokens=4096)
        self.tool = FlightSearchTool()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")

        # 提取 IATA 码（简化：直接用城市名，实际需要 IATA 转换）
        from_city = state.get("departure_city", "")
        to_city = state.get("destination", "")
        strategy = state.get("current_strategy", {})
        flight_pref = strategy.get("strategy", {}).get("flight_preference", "balanced")

        # 获取 IATA 码映射（未知城市直接降级，不生成非法码）
        origin_iata = await self._city_to_iata(from_city)
        dest_iata = await self._city_to_iata(to_city)

        if not origin_iata or not dest_iata:
            logger.warning("[%s] 未知城市 IATA，跳过航班搜索：%s → %s", trip_id, from_city, to_city)
            return {"flight_candidates": []}

        try:
            # 调用工具搜索
            raw_result = await self.tool._arun(
                origin=origin_iata,
                destination=dest_iata,
                departure_date=state.get("start_date", ""),
                return_date=state.get("end_date", ""),
                adults=len(state.get("travelers", [{"age": 30}])),
            )

            tool_data = json.loads(raw_result)
            candidates_raw = tool_data.get("candidates", [])

            if not candidates_raw:
                logger.warning("[%s] 未找到航班", trip_id)
                return {"flight_candidates": []}

            # LLM 排序推理
            prompt = (
                f"偏好：{flight_pref}\n出发：{from_city}({origin_iata}) → {to_city}({dest_iata})\n"
                f"日期：{state.get('start_date')} ~ {state.get('end_date')}\n"
                f"原始结果：{json.dumps(candidates_raw, ensure_ascii=False)}"
            )

            messages = [
                SystemMessage(content=FLIGHT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            parsed = self._parse_json(content)
            candidates = parsed.get("candidates", candidates_raw) if parsed else candidates_raw

            logger.info("[%s] FlightAgent 完成：%d 个候选航班", trip_id, len(candidates))
            return {"flight_candidates": candidates}

        except Exception as e:
            logger.exception("[%s] FlightAgent 失败: %s", trip_id, e)
            return {"flight_candidates": []}

    async def _city_to_iata(self, city: str) -> str | None:
        """城市名 → 主机场 IATA 码（未知返回 None，交由调用方降级）"""
        from app.core.geocode import city_to_flight_iata

        return city_to_flight_iata(city)

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
