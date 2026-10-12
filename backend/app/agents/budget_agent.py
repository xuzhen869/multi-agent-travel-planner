"""预算核算 Agent — 汇总费用并对比用户预算"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

BUDGET_SYSTEM_PROMPT = """你是一个旅行预算核算专家。根据行程内容核算各项费用：

## 费用分类
1. flights：选择的往返航班总价
2. hotels：酒店每晚价格 × 入住天数
3. attractions：每日景点门票合计
4. meals：每日餐饮估算（根据 meal_budget_per_day × 天数 × 人数）
5. transport_local：市内交通（地铁/巴士/打车，默认¥50/人/天）
6. visa_insurance：签证+保险（出境默认¥600）
7. misc：其他杂费（小费/购物/通讯，默认预算的 5%）

## 输出格式（严格 JSON）
{
  "breakdown": {
    "flights": 6300,
    "hotels": 5600,
    "attractions": 1200,
    "meals": 3500,
    "transport_local": 800,
    "visa_insurance": 600,
    "misc": 1000
  },
  "total": 19000,
  "budget_total": 20000,
  "budget_remaining": 1000,
  "currency": "CNY",
  "overspent_items": [],
  "warnings": ["餐饮预算偏低"]
}"""


class BudgetAgent(BaseAgent):
    """预算核算 Agent"""

    name = "budget_agent"
    description = "汇总费用并对比用户预算"

    def __init__(self):
        self.llm = get_llm(temperature=0.2, max_tokens=4096)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")
        strategy = state.get("current_strategy", {})

        try:
            itinerary = state.get("itinerary", {})
            flights = state.get("flight_candidates", [])
            hotels = state.get("hotel_candidates", [])
            budget_input = state.get("budget", {})
            travelers = len(state.get("travelers", [{"age": 30}]))
            meal_budget = strategy.get("strategy", {}).get("meal_budget_per_day", 400)

            # 计算天数
            days = self._count_days(state.get("start_date", ""), state.get("end_date", ""))

            input_data = {
                "itinerary_summary": f"{len(itinerary.get('days', []))} 天行程",
                "flights_summary": f"最低价 ¥{min([f.get('total_price', 99999) for f in flights]) if flights else '未知'}",
                "hotels_summary": f"{len(hotels)} 个候选",
                "budget_total": budget_input.get("total", 20000),
                "travelers": travelers,
                "days": days,
                "meal_budget_per_day": meal_budget,
                "days_detail": [
                    {"date": d.get("date", ""), "day_budget": d.get("day_budget_estimate", 0)}
                    for d in itinerary.get("days", [])
                ],
            }

            messages = [
                SystemMessage(content=BUDGET_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(input_data, ensure_ascii=False)),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            budget_result = self._parse_json(content)
            if not budget_result or not budget_result.get("breakdown"):
                logger.warning("[%s] BudgetAgent 无有效 LLM 输出，使用规则兜底", trip_id)
                budget_result = self._rule_based_budget(state, strategy)

            logger.info("[%s] BudgetAgent 完成：总计 ¥%s", trip_id, budget_result.get("total", 0))
            return {"budget_result": budget_result}

        except Exception as e:
            logger.exception("[%s] BudgetAgent 失败: %s", trip_id, e)
            return {"budget_result": self._rule_based_budget(state, strategy)}

    def _rule_based_budget(self, state: dict[str, Any], strategy: dict) -> dict:
        """规则兜底预算：不依赖 LLM，按默认单价估算，保证 total/breakdown 有效。"""
        budget_input = state.get("budget", {}) or {}
        total_budget = budget_input.get("total", 20000)
        currency = budget_input.get("currency", "CNY")
        travelers = len(state.get("travelers", [{"age": 30}]))
        days = self._count_days(state.get("start_date", ""), state.get("end_date", ""))
        meal_budget = (strategy.get("strategy") or {}).get("meal_budget_per_day", 400)

        flights = state.get("flight_candidates", []) or []
        hotels = state.get("hotel_candidates", []) or []
        flight_price = min([f.get("total_price", 99999) for f in flights], default=8000)
        hotel_price = hotels[0].get("price_per_night_estimate", 500) if hotels else 500

        breakdown = {
            "flights": round(flight_price * travelers),
            "hotels": round(hotel_price * days),
            "attractions": round(150 * days * travelers),
            "meals": round(meal_budget * days * travelers),
            "transport_local": round(50 * days * travelers),
            "visa_insurance": 600,
            "misc": round(total_budget * 0.05),
        }
        total = sum(breakdown.values())
        return {
            "breakdown": breakdown,
            "total": total,
            "budget_total": total_budget,
            "budget_remaining": total_budget - total,
            "currency": currency,
            "overspent_items": [k for k, v in breakdown.items() if v > total_budget * 0.5],
            "warnings": ["估算数据，未使用实时价格"],
            "source": "rule_fallback",
        }

    def _count_days(self, start: str, end: str) -> int:
        try:
            from datetime import datetime
            return max(1, (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days)
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
