"""行程编排 Agent — 按时间线拼接每日行程

输入：航班 + 酒店 + POI 候选集 + 用户偏好 + 推荐策略
输出：按天排列的结构化行程
"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

ITINERARY_SYSTEM_PROMPT = """你是一个旅行行程编排专家。根据以下信息编排每日行程：

## 输入信息
- 航班到达/出发时间
- 酒店位置和入住/退房时间
- 景点/餐厅候选列表（含位置、开放时间、建议游览时长、评分）
- 用户偏好节奏（relaxed=每天2个主要活动 / moderate=每天3个 / intensive=每天4个）

## 编排规则
1. 地理聚类：同区域的景点安排在同一天，减少交通时间
2. 时间可行性：确保景点在开放时间内，活动间预留交通时间（默认15分钟/次）
3. 节奏控制：午餐、晚餐时间各预留60-90分钟
4. 到达日和离开日：航班时间前后的空隙安排轻量活动
5. 每天至少安排 1 个午餐点和 1 个晚餐点

## 输出格式（严格 JSON）
{
  "days": [
    {
      "date": "2026-10-01",
      "label": "抵达日",
      "flight_inbound": {"arrival_time": "13:00", ...},
      "hotel_checkin": {"name": "新宿酒店", "time": "14:00"},
      "activities": [
        {"time": "14:00", "type": "checkin", "name": "酒店入住", "poi_id": "HT-001"},
        {"time": "15:00", "type": "attraction", "name": "新宿御苑", "poi_id": "POI-005", "duration_min": 90, "notes": "赏枫好时节"},
        {"time": "18:00", "type": "dinner", "name": "叙叙苑烧肉", "poi_id": "RST-003", "notes": "人气烧肉店，建议预约"}
      ],
      "transport": [
        {"from": "酒店", "to": "新宿御苑", "mode": "步行", "duration_min": 10, "estimated_cost": 0}
      ],
      "day_budget_estimate": 800
    }
  ]
}

每个 daily 对象必须包含：date, label, activities（至少1个）, transport（至少1个）, day_budget_estimate"""


class ItineraryAgent(BaseAgent):
    """行程编排 Agent"""

    name = "itinerary_agent"
    description = "按时间线编排每日行程"

    def __init__(self):
        self.llm = get_llm(temperature=0.5, max_tokens=16384)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")
        strategy = state.get("current_strategy", {})

        try:
            # 构建编排输入
            input_data = {
                "destination": state.get("destination", ""),
                "dates": {"start": state.get("start_date", ""), "end": state.get("end_date", "")},
                "flight_candidates": state.get("flight_candidates", [])[:3],
                "hotel_candidates": state.get("hotel_candidates", [])[:3],
                "attractions": state.get("poi_data", {}).get("attractions", []),
                "restaurants": state.get("poi_data", {}).get("restaurants", []),
                "strategy": strategy.get("strategy", {}),
                "pace": strategy.get("strategy", {}).get("pace", "moderate"),
                "poi_weight": strategy.get("strategy", {}).get("poi_weight", {}),
            }

            prompt = json.dumps(input_data, ensure_ascii=False, indent=2)

            messages = [
                SystemMessage(content=ITINERARY_SYSTEM_PROMPT),
                HumanMessage(content=f"请编排以下旅行行程：\n\n{prompt}"),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            itinerary = self._parse_json(content)
            if not itinerary or not itinerary.get("days"):
                logger.warning("[%s] ItineraryAgent 无有效 LLM 输出，使用规则兜底", trip_id)
                itinerary = self._rule_based_itinerary(state)

            logger.info("[%s] ItineraryAgent 完成：%d 天", trip_id, len(itinerary.get("days", [])))
            return {"itinerary": itinerary}

        except Exception as e:
            logger.exception("[%s] ItineraryAgent 失败: %s", trip_id, e)
            # 规则兜底保证 days 非空，避免 Synthesizer 过滤掉全部方案
            return {"itinerary": self._rule_based_itinerary(state)}

    def _rule_based_itinerary(self, state: dict[str, Any]) -> dict:
        """规则兜底行程：不依赖 LLM，保证 days 非空。

        基于出发/返回日期生成每日骨架；若已采集到航班/酒店候选，
        在抵达/离开日注入对应信息；日活动为不依赖外部 POI 的通用安排。
        这样在 LLM 或外部数据源不可用时，Synthesizer 仍有可用方案。
        """
        from datetime import datetime, timedelta

        destination = state.get("destination", "目的地")
        start = state.get("start_date", "")
        end = state.get("end_date", "")

        try:
            d0 = datetime.strptime(start, "%Y-%m-%d")
            d1 = datetime.strptime(end, "%Y-%m-%d")
            day_count = max(1, (d1 - d0).days + 1)
        except Exception:
            d0 = datetime.now()
            day_count = 5

        strategy = state.get("current_strategy", {}) or {}
        strategy_cfg = strategy.get("strategy", {}) or {}
        pace = strategy_cfg.get("pace", "moderate")
        main_acts = {"relaxed": 2, "moderate": 3, "intensive": 4}.get(pace, 3)
        meal_budget = strategy_cfg.get("meal_budget_per_day", 400)

        flight = (state.get("flight_candidates") or [None])[0]
        hotel = (state.get("hotel_candidates") or [None])[0]

        days = []
        for i in range(day_count):
            date = (d0 + timedelta(days=i)).strftime("%Y-%m-%d")
            is_first = i == 0
            is_last = i == day_count - 1 and day_count > 1

            if is_first:
                label = "抵达日"
            elif is_last:
                label = "离开日"
            else:
                label = f"第 {i + 1} 天"

            activities = []

            # 抵达/离开日的航班与入住信息
            if is_first and flight:
                activities.append({
                    "time": "09:00", "type": "checkin",
                    "name": f"抵达 {destination}",
                    "notes": "机场到市区建议预留 1 小时交通", "duration_min": 120,
                })
            if is_first and hotel:
                activities.append({
                    "time": "14:00", "type": "checkin",
                    "name": hotel.get("name", "酒店入住"),
                    "poi_id": hotel.get("id"), "duration_min": 60,
                })
            if is_last and flight:
                activities.append({
                    "time": "16:00", "type": "transport",
                    "name": f"从 {destination} 返程", "duration_min": 120,
                })

            # 通用日活动补齐到 pace 要求的数量
            template = [
                {"time": "09:30", "type": "attraction", "name": f"漫步{destination}城市中心",
                 "duration_min": 120, "notes": "感受当地氛围"},
                {"time": "12:00", "type": "lunch", "name": "品尝当地特色美食",
                 "duration_min": 60, "notes": "推荐当地人气餐厅"},
                {"time": "14:30", "type": "attraction", "name": f"参观{destination}地标景点",
                 "duration_min": 120, "notes": "核心打卡点"},
                {"time": "18:00", "type": "dinner", "name": "体验地道晚餐",
                 "duration_min": 90, "notes": "根据口味偏好选择"},
            ]
            existing = len(activities)
            for base in template[: max(0, main_acts - existing)]:
                activities.append(base)

            transport = []
            if len(activities) >= 2:
                transport.append({"from": "住宿", "to": f"{destination}城市中心", "mode": "地铁/巴士",
                                  "duration_min": 30, "estimated_cost": 50})
            if len(activities) >= 3:
                transport.append({"from": f"{destination}城市中心", "to": f"{destination}地标景点",
                                  "mode": "步行", "duration_min": 15, "estimated_cost": 0})

            days.append({
                "date": date,
                "label": label,
                "activities": activities,
                "transport": transport,
                "day_budget_estimate": meal_budget + 300,
            })

        return {"days": days}

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
