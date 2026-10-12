"""结果合成 Agent — 将多路输出合并为最终格式"""

import json
import logging
from typing import Any

from app.core.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.config import settings

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """你是一个旅行方案合成专家。将多个方案的行程数据合并为最终的统一格式输出。

## 输出格式（严格 JSON，针对推荐模式输出多方案）
{
  "user_profile": {"label": "...", "traits": [...]},
  "weather": [...],
  "plans": [
    {
      "id": "plan_a",
      "title": "高性价比之旅",
      "reason": "花的每分钱都值得",
      "budget_breakdown": {...},
      "total_cost": 14200,
      "itinerary": {...},
      "highlights": ["亮点1", "亮点2", "亮点3"]
    }
  ]
}

要求：
1. 每个方案保留原始 id、title、reason（≤10字）
2. highlights 是 3 个清晰的行程亮点
3. weather 从 poi_data 中透传
4. 如果某个方案生成失败（有 error 字段），跳过该方案
5. 至少保证 1 个可用方案"""


class Synthesizer(BaseAgent):
    """结果合成 Agent"""

    name = "synthesizer"
    description = "合并多路输出为最终格式"

    def __init__(self):
        self.llm = get_llm(temperature=0.3, max_tokens=16384)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        trip_id = state.get("trip_id", "")

        try:
            plan_results = state.get("plan_results", [])
            user_profile = state.get("user_profile", {})
            # 提取天气（来自 poi_data）
            poi_data = state.get("poi_data", {}) or {}
            weather = poi_data.get("weather", None)

            # 过滤掉失败的方案
            valid_plans = []
            for plan in plan_results:
                if plan.get("error"):
                    logger.warning("[%s] 跳过失败方案 %s: %s", trip_id, plan.get("id"), plan["error"])
                    continue
                if not plan.get("itinerary") or not plan["itinerary"].get("days"):
                    logger.warning("[%s] 跳过空行程方案 %s", trip_id, plan.get("id"))
                    continue
                valid_plans.append(plan)

            if not valid_plans:
                logger.error("[%s] Synthesizer：没有可用方案", trip_id)
                return self._empty_output()

            # 如果只有 1-2 个方案，直接组装（不需要 LLM）
            if len(valid_plans) <= 2:
                output = self._build_output(user_profile, valid_plans, weather)
            else:
                # 用 LLM 提取亮点；失败时降级为规则组装，保证结果可用
                try:
                    output = await self._llm_synthesize(user_profile, valid_plans)
                except Exception as e:
                    logger.warning("[%s] LLM 合成失败，降级规则组装: %s", trip_id, e)
                    output = self._build_output(user_profile, valid_plans, weather)
                if weather:
                    output["weather"] = weather

            logger.info("[%s] Synthesizer 完成：%d 个方案", trip_id, len(output.get("plans", [])))
            return {"final_output": output}

        except Exception as e:
            logger.exception("[%s] Synthesizer 失败: %s", trip_id, e)
            return {"final_output": self._empty_output()}

    def _build_output(self, user_profile: dict, plans: list[dict], weather: list | None = None) -> dict:
        """直接组装输出（≤2 个方案时跳过 LLM）"""
        output_plans = []
        for plan in plans:
            itinerary = plan.get("itinerary", {})
            budget = plan.get("budget", {})

            # 提取亮点：每天的第一个景点
            highlights = []
            for day in itinerary.get("days", [])[:3]:
                for act in day.get("activities", []):
                    if act.get("type") == "attraction":
                        highlights.append(act.get("name", ""))
                        break

            output_plans.append({
                "id": plan.get("id", ""),
                "title": plan.get("title", ""),
                "reason": plan.get("reason", ""),
                "budget_breakdown": budget.get("breakdown", {}),
                "total_cost": budget.get("total", 0),
                "itinerary": itinerary,
                "highlights": highlights[:3] if highlights else ["精彩行程等你探索"],
            })

        result: dict = {
            "user_profile": user_profile,
            "plans": output_plans,
        }
        if weather:
            result["weather"] = weather
        return result

    async def _llm_synthesize(self, user_profile: dict, plans: list[dict]) -> dict:
        """LLM 辅助合成（≥3 个方案时提取亮点）"""
        # 精简输入（去掉完整 detail）
        simplified = []
        for plan in plans:
            itinerary = plan.get("itinerary", {})
            days_summary = []
            for day in itinerary.get("days", []):
                activities = [a.get("name", "") for a in day.get("activities", [])]
                days_summary.append(f"{day.get('date', '')} {day.get('label', '')}: {', '.join(activities)}")

            simplified.append({
                "id": plan.get("id"),
                "title": plan.get("title"),
                "reason": plan.get("reason"),
                "total_cost": plan.get("budget", {}).get("total", 0),
                "budget_breakdown": plan.get("budget", {}).get("breakdown", {}),
                "days_summary": days_summary,
                "itinerary": itinerary,
            })

        prompt = json.dumps({
            "user_profile": user_profile,
            "plans": simplified,
        }, ensure_ascii=False, indent=2)

        messages = [
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=f"合成以下旅行方案：\n\n{prompt}"),
        ]
        response = await self.llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        parsed = self._parse_json(content)
        if not parsed:
            return self._build_output(user_profile, plans)
        # LLM 输出不可控，做字段级清洗兜底，保证前端契约完整
        return self._sanitize_output(parsed, plans)

    def _sanitize_output(self, output: dict, raw_plans: list[dict]) -> dict:
        """清洗 LLM 合成输出：补齐缺失字段（total_cost/id/highlights 等）。

        LLM 可能省略或改错字段，直接用原始 plan 数据回填，避免前端拿到 undefined。
        """
        raw_by_id = {p.get("id"): p for p in raw_plans}
        plans = output.get("plans") or []
        cleaned = []
        for p in plans:
            if not isinstance(p, dict):
                continue
            raw = raw_by_id.get(p.get("id")) or raw_by_id.get("plan_direct") or {}
            budget = raw.get("budget") or {}
            cleaned.append({
                "id": p.get("id", raw.get("id", "")),
                "title": p.get("title", raw.get("title", "旅行方案")),
                "reason": p.get("reason", raw.get("reason", "")),
                "total_cost": p.get("total_cost", budget.get("total", 0)),
                "budget_breakdown": p.get("budget_breakdown", budget.get("breakdown", {})),
                "itinerary": p.get("itinerary", raw.get("itinerary", {})),
                "highlights": p.get("highlights") or raw.get("highlights") or ["精彩行程等你探索"],
            })
        output["plans"] = cleaned
        return output

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

    def _empty_output(self) -> dict:
        return {
            "user_profile": {"label": "旅行者", "traits": []},
            "plans": [],
            "error": "未能生成可用方案",
        }
