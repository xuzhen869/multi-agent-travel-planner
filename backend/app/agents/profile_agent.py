"""用户画像 + 推荐策略 Agent

根据用户偏好数据 → LLM 推理 → 生成用户画像标签 + 2-3 套推荐策略
"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

# ——— System Prompt ———

PROFILE_SYSTEM_PROMPT = """你是一个专业的旅行用户画像分析师。你的任务是：

1. 根据用户的旅行偏好和人口统计信息，生成一句简洁的用户画像标签（≤12 字）
2. 分析用户的核心特征（3-5 个关键词）
3. 生成 2-3 套差异化的旅行推荐策略

每套策略必须包含：
- id: 唯一标识（plan_a / plan_b / plan_c）
- title: 策略名称（简洁有吸引力，≤8 字）
- reason: 推荐理由（≤10 字）
- strategy: 具体的策略参数（hotel_star_override, flight_preference, pace, poi_weight, meal_budget_per_day, description）

## 策略区分维度
- 预算分配：省钱优先 vs 体验优先
- 兴趣侧重：美食 vs 景点 vs 购物 vs 深度文化
- 节奏：紧凑打卡 vs 松弛享受

## 输出格式（严格 JSON，不要包含 markdown 代码块标记）
{
  "user_profile": {
    "label": "年轻情侣·美食文化派",
    "traits": ["双人出行", "偏好舒适体验", "对美食有要求"],
    "budget_flexibility": "moderate"
  },
  "recommendations": [
    {
      "id": "plan_a",
      "title": "高性价比之旅",
      "reason": "花的每分钱都值得",
      "strategy": {
        "hotel_star_override": 3,
        "flight_preference": "cheapest",
        "pace": "moderate",
        "poi_weight": {"free_attractions": 0.7, "paid_attractions": 0.3},
        "meal_budget_per_day": 300,
        "description": "优先低价航班和三星酒店，景点选择免费或低价，餐饮以当地小吃为主"
      }
    }
  ]
}"""


class ProfileAgent(BaseAgent):
    """用户画像分析 Agent"""

    name = "profile_agent"
    description = "根据旅行偏好生成用户画像和推荐策略"

    def __init__(self):
        self.llm = get_llm(temperature=0.7, max_tokens=2048)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """执行画像分析"""
        trip_id = state.get("trip_id", "")

        # 构建输入
        user_input = {
            "departure_city": state.get("departure_city", ""),
            "destination": state.get("destination", ""),
            "dates": {
                "start": state.get("start_date", ""),
                "end": state.get("end_date", ""),
            },
            "travelers": state.get("travelers", []),
            "budget": state.get("budget", {}),
            "preferences": state.get("preferences", {}),
        }

        input_text = json.dumps(user_input, ensure_ascii=False, indent=2)

        try:
            messages = [
                SystemMessage(content=PROFILE_SYSTEM_PROMPT),
                HumanMessage(content=f"根据以下旅行者信息生成用户画像和推荐策略：\n\n{input_text}"),
            ]
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            # 解析 JSON 输出
            parsed = self._parse_json(content)
            if not parsed:
                parsed = self._fallback_profile()

            result = {
                "user_profile": parsed.get("user_profile", {}),
                "strategies": parsed.get("recommendations", []),
            }
            logger.info("[%s] ProfileAgent 完成：%s, %d 套策略", trip_id, result["user_profile"].get("label", ""), len(result["strategies"]))

            return result

        except Exception as e:
            logger.exception("[%s] ProfileAgent 失败: %s", trip_id, e)
            return {
                "user_profile": self._fallback_profile()["user_profile"],
                "strategies": self._fallback_profile()["recommendations"],
            }

    def _parse_json(self, text: str) -> dict | None:
        """从 LLM 输出中解析 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试提取 ```json ... ``` 代码块
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试提取 { ... } 块
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _fallback_profile(self) -> dict:
        """LLM 失败时的兜底画像"""
        return {
            "user_profile": {
                "label": "旅行探索者",
                "traits": ["热爱旅行", "注重体验"],
                "budget_flexibility": "moderate",
            },
            "recommendations": [
                {
                    "id": "plan_a",
                    "title": "高性价比之旅",
                    "reason": "花的每分钱都值得",
                    "strategy": {
                        "hotel_star_override": 3,
                        "flight_preference": "cheapest",
                        "pace": "moderate",
                        "poi_weight": {"free_attractions": 0.7, "paid_attractions": 0.3},
                        "meal_budget_per_day": 300,
                        "description": "优先低价航班和三星酒店",
                    },
                },
                {
                    "id": "plan_b",
                    "title": "经典打卡之旅",
                    "reason": "不错过每一个经典",
                    "strategy": {
                        "hotel_star_override": 4,
                        "flight_preference": "balanced",
                        "pace": "intensive",
                        "poi_weight": {"attractions": 0.7, "restaurants": 0.3},
                        "meal_budget_per_day": 400,
                        "description": "舒适住宿，覆盖必去景点",
                    },
                },
                {
                    "id": "plan_c",
                    "title": "深度慢游之旅",
                    "reason": "像当地人一样生活",
                    "strategy": {
                        "hotel_star_override": 4,
                        "flight_preference": "balanced",
                        "pace": "relaxed",
                        "poi_weight": {"local_experience": 0.5, "attractions": 0.3, "restaurants": 0.2},
                        "meal_budget_per_day": 500,
                        "description": "融入当地生活节奏",
                    },
                },
            ],
        }
