"""约束校验 Agent — 检查硬约束违规 + 软约束警告"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

CONSTRAINT_SYSTEM_PROMPT = """你是一个旅行约束校验专家。逐项检查行程是否符合约束：

## 硬约束（必须通过，否则行程不可用）
1. 景点开放时间：活动时间必须在景点开放时间内
2. 时间冲突：相邻活动之间必须预留合理的交通时间（≥15分钟）
3. 休馆日检查：景点不能安排在其休馆日（如果有信息）
4. 超预算：总费用不能超出预算的 20%

## 软约束（警告即可）
5. 行程密度：每天活动数量应与 pace 匹配
   - relaxed: 2-3 个主要活动
   - moderate: 3-4 个主要活动
   - intensive: 4-5 个主要活动
6. 餐饮匹配：菜系应与 dietary 偏好不冲突
7. 酒店星级：不应显著低于偏好（最多差 1 星）

## 输出格式（严格 JSON）
{
  "passed": true,
  "violations": [
    {
      "type": "hard",
      "item": "Day3 PM 筑地市场",
      "desc": "筑地市场周三休市，但 Day3 是周三",
      "fix_by": "itinerary",
      "suggestion": "将筑地市场换到 Day4（周四）"
    }
  ]
}

- passed: true 表示无硬约束违规
- fix_by: "flight" | "hotel" | "itinerary" | "budget"（回退到哪个 Agent 修复）
- 如果没有违规，violations 为空数组 []"""


class ConstraintAgent(BaseAgent):
    """约束校验 Agent"""

    name = "constraint_agent"
    description = "检查硬约束违规和软约束警告"

    def __init__(self):
        self.llm = get_llm(temperature=0.1, max_tokens=4096)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")
        strategy = state.get("current_strategy", {})

        try:
            check_input = {
                "itinerary": state.get("itinerary", {}),
                "budget": state.get("budget_result", {}),
                "pace": strategy.get("strategy", {}).get("pace", "moderate"),
                "dietary": state.get("preferences", {}).get("dietary", []),
                "preferred_hotel_star": state.get("preferences", {}).get("hotel_star", 4),
                "hotel_candidates": state.get("hotel_candidates", [])[:1],
            }

            messages = [
                SystemMessage(content=CONSTRAINT_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(check_input, ensure_ascii=False, indent=2)),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            result = self._parse_json(content)
            if not result:
                result = {"passed": True, "violations": []}

            passed = result.get("passed", True)
            violations = result.get("violations", [])

            if violations:
                hard_count = sum(1 for v in violations if v.get("type") == "hard")
                logger.info("[%s] ConstraintAgent：%d 违规（%d 硬约束）", trip_id, len(violations), hard_count)
            else:
                logger.info("[%s] ConstraintAgent：全部通过", trip_id)

            return {
                "constraint_passed": passed,
                "violations": violations,
            }

        except Exception as e:
            logger.exception("[%s] ConstraintAgent 失败: %s", trip_id, e)
            return {"constraint_passed": True, "violations": []}

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
