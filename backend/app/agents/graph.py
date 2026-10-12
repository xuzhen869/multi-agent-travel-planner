"""LangGraph StateGraph — 旅行规划的完整有向图

工作流：
  START → ProfileAgent → 并行数据采集(Flight∥Hotel∥POI)
  → 推荐分叉（每个策略经 Itinerary→Budget→Constraint，最多3轮回退）
  → Synthesizer → END

使用 LangGraph Send API 实现 map-reduce 模式的策略分叉。
"""

import logging
import asyncio
from typing import TypedDict, Any, Annotated
import operator

from langgraph.graph import StateGraph, END
from langgraph.constants import Send

logger = logging.getLogger(__name__)


# ——— 共享状态 ———


class PlannerState(TypedDict, total=False):
    """LangGraph 共享状态 — 各 Agent 通过此字典传递数据。"""

    # ——— 输入 ———
    trip_id: str
    departure_city: str
    destination: str
    start_date: str
    end_date: str
    travelers: list[dict]
    budget: dict
    preferences: dict
    mode: str

    # ——— ProfileAgent 输出 ———
    user_profile: dict | None
    strategies: list[dict] | None

    # ——— 当前策略（分叉时注入） ———
    current_strategy: dict | None

    # ——— Flight/Hotel/POI Agent 输出 ———
    flight_candidates: list[dict]
    hotel_candidates: list[dict]
    poi_data: dict | None

    # ——— Per-strategy 输出（operator.add reducer 自动合并） ———
    plan_results: Annotated[list[dict], operator.add]

    # ——— Synthesizer 输出 ———
    final_output: dict | None

    # ——— 错误 ———
    errors: list[dict] | None


# ——— 节点函数（全部 async，LangGraph 原生支持） ———


async def _profile_node(state: PlannerState) -> dict:
    """ProfileAgent 节点"""
    from app.agents.profile_agent import ProfileAgent

    agent = ProfileAgent()
    result = await agent.run(state)
    logger.info("[%s] LangGraph → ProfileAgent 完成", state.get("trip_id", ""))
    return result


def _direct_strategy(state: PlannerState) -> dict:
    """构建默认直接规划策略（direct 模式与空 strategies 兜底共用）"""
    return {
        "id": "plan_direct",
        "title": "直接规划",
        "reason": "定制行程",
        "strategy": {
            "hotel_star_override": state.get("preferences", {}).get("hotel_star", 4),
            "flight_preference": "balanced",
            "pace": state.get("preferences", {}).get("pace", "moderate"),
            "poi_weight": {"attractions": 0.5, "restaurants": 0.5},
            "meal_budget_per_day": 400,
            "description": "平衡的旅行规划",
        },
    }


async def _direct_setup_node(state: PlannerState) -> dict:
    """直接模式：注入默认策略"""
    return {"strategies": [_direct_strategy(state)]}


async def _flight_node(state: PlannerState) -> dict:
    """FlightAgent 节点"""
    from app.agents.flight_agent import FlightAgent

    agent = FlightAgent()
    result = await agent.run(state)
    logger.info("[%s] LangGraph → FlightAgent 完成", state.get("trip_id", ""))
    return result


async def _hotel_node(state: PlannerState) -> dict:
    """HotelAgent 节点"""
    from app.agents.hotel_agent import HotelAgent

    agent = HotelAgent()
    result = await agent.run(state)
    logger.info("[%s] LangGraph → HotelAgent 完成", state.get("trip_id", ""))
    return result


async def _poi_node(state: PlannerState) -> dict:
    """POIAgent 节点"""
    from app.agents.poi_agent import POIAgent

    agent = POIAgent()
    result = await agent.run(state)
    logger.info("[%s] LangGraph → POIAgent 完成", state.get("trip_id", ""))
    return result


async def _data_collection_node(state: PlannerState) -> dict:
    """数据采集节点 — Flight ∥ Hotel ∥ POI 并行执行"""
    from app.agents.flight_agent import FlightAgent
    from app.agents.hotel_agent import HotelAgent
    from app.agents.poi_agent import POIAgent

    trip_id = state.get("trip_id", "")

    flight_agent = FlightAgent()
    hotel_agent = HotelAgent()
    poi_agent = POIAgent()

    flight_task = flight_agent.run(state)
    hotel_task = hotel_agent.run(state)
    poi_task = poi_agent.run(state)

    results = await asyncio.gather(flight_task, hotel_task, poi_task, return_exceptions=True)

    merged: dict = {"flight_candidates": [], "hotel_candidates": [], "poi_data": {"attractions": [], "restaurants": []}}

    for name, result, key in [
        ("FlightAgent", results[0], "flight_candidates"),
        ("HotelAgent", results[1], "hotel_candidates"),
        ("POIAgent", results[2], "poi_data"),
    ]:
        if isinstance(result, Exception):
            logger.error("[%s] LangGraph → %s 失败: %s", trip_id, name, result)
        elif isinstance(result, dict):
            merged[key] = result.get(key, [] if key != "poi_data" else {"attractions": [], "restaurants": []})

    logger.info("[%s] LangGraph → 数据采集完成", trip_id)
    return merged


async def _process_strategy_node(state: PlannerState) -> dict:
    """处理单个策略：ItineraryAgent → BudgetAgent → ConstraintAgent（最多 3 轮回退）

    此节点被 Send API 为每个 strategy 各调用一次。plan_results 使用 operator.add reducer。
    """
    from app.agents.itinerary_agent import ItineraryAgent
    from app.agents.budget_agent import BudgetAgent
    from app.agents.constraint_agent import ConstraintAgent
    from app.agents.flight_agent import FlightAgent
    from app.agents.hotel_agent import HotelAgent
    from app.services.progress_service import ProgressService

    trip_id = state.get("trip_id", "")
    strategy = state.get("current_strategy", {})
    plan_id = strategy.get("id", "unknown")
    plan_title = strategy.get("title", "")
    plan_reason = strategy.get("reason", "")
    plan_state = dict(state)

    try:
        itinerary_agent = ItineraryAgent()
        budget_agent = BudgetAgent()
        constraint_agent = ConstraintAgent()
        flight_agent = FlightAgent()
        hotel_agent = HotelAgent()

        # 方案开始生成
        await ProgressService.publish_plan_start(trip_id, plan_id, plan_title, plan_reason)

        # 编排行程
        await ProgressService.publish_plan_agent_start(trip_id, plan_id, "ItineraryAgent", "itinerary", "正在编排行程...")
        itin_result = await itinerary_agent.run(plan_state)
        plan_state.update(itin_result)
        await ProgressService.publish_plan_agent_complete(trip_id, plan_id, "ItineraryAgent", "itinerary", "行程编排完成")

        # 核算预算
        await ProgressService.publish_plan_agent_start(trip_id, plan_id, "BudgetAgent", "budget", "正在核算预算...")
        budget_result = await budget_agent.run(plan_state)
        plan_state.update(budget_result)
        await ProgressService.publish_plan_agent_complete(trip_id, plan_id, "BudgetAgent", "budget", "预算核算完成")

        # 约束校验（最多 3 轮回退，按 violations 的 fix_by 选择修复 Agent）
        for retry in range(3):
            await ProgressService.publish_plan_agent_start(trip_id, plan_id, "ConstraintAgent", "constraint", "正在校验约束...")
            const_result = await constraint_agent.run(plan_state)
            plan_state.update(const_result)
            await ProgressService.publish_plan_agent_complete(trip_id, plan_id, "ConstraintAgent", "constraint", "约束校验完成")

            if plan_state.get("constraint_passed", True):
                break

            fix_agent = _resolve_fix_agent(
                const_result.get("violations", []),
                itinerary_agent, budget_agent, flight_agent, hotel_agent,
            )
            fix_result = await fix_agent.run(plan_state)
            plan_state.update(fix_result)
            await ProgressService.publish_plan_agent_start(
                trip_id, plan_id, fix_agent.name, "constraint",
                f"约束未通过，正在修复（第 {retry + 1} 轮）",
            )
            await ProgressService.publish_plan_agent_complete(
                trip_id, plan_id, fix_agent.name, "constraint", "修复完成",
            )
            logger.info("[%s] 方案 %s 约束回退到 %s（第 %d 轮）", trip_id, plan_id, fix_agent.name, retry + 1)

        # 方案就绪（携带预算成本，供前端方框展示价格）
        budget_data = plan_state.get("budget_result", {})
        plan_cost = 0
        if isinstance(budget_data, dict):
            plan_cost = budget_data.get("total", 0) or 0
        await ProgressService.publish_plan_ready(trip_id, plan_id, plan_title, plan_reason, float(plan_cost))

        return {
            "plan_results": [{
                "id": plan_id,
                "title": strategy.get("title", ""),
                "reason": strategy.get("reason", ""),
                "itinerary": plan_state.get("itinerary", {}),
                "budget": plan_state.get("budget_result", {}),
                "constraints": {
                    "passed": plan_state.get("constraint_passed", True),
                    "violations": plan_state.get("violations", []),
                },
            }],
        }

    except Exception as e:
        logger.exception("[%s] 方案 %s 生成失败: %s", trip_id, plan_id, e)
        return {
            "plan_results": [{
                "id": plan_id,
                "title": strategy.get("title", ""),
                "reason": strategy.get("reason", ""),
                "error": str(e),
            }],
        }


async def _synthesizer_node(state: PlannerState) -> dict:
    """Synthesizer 节点"""
    from app.agents.synthesizer import Synthesizer

    agent = Synthesizer()
    result = await agent.run(state)
    logger.info("[%s] LangGraph → Synthesizer 完成", state.get("trip_id", ""))
    return result


# ——— 条件路由 ———


def _route_after_profile(state: PlannerState) -> str:
    """推荐模式用 profile 结果；直接模式走 direct_setup"""
    if state.get("mode", "recommend") == "direct":
        return "direct_setup"
    return "data_collection"


def _fan_out_strategies(state: PlannerState) -> list[Send]:
    """将每个 strategy 映射为一个 process_strategy 节点调用（LangGraph map-reduce）。

    若 strategies 为空（如 ProfileAgent 无可用策略），注入默认直接策略兜底，
    保证图中始终至少有一个方案进入流程，而不是空分叉导致 0 方案静默完成。
    """
    strategies = state.get("strategies", [])
    if not strategies:
        logger.warning("没有可用策略，注入默认直接规划策略兜底")
        strategies = [_direct_strategy(state)]

    return [
        Send("process_strategy", {**state, "current_strategy": s})
        for s in strategies
    ]


def _resolve_fix_agent(
    violations: list[dict],
    itinerary_agent: Any,
    budget_agent: Any,
    flight_agent: Any,
    hotel_agent: Any,
) -> Any:
    """根据约束违规的 fix_by 决定回退到哪个 Agent 修复；默认回退 itinerary。

    与 ConstraintAgent 的 fix_by 协议保持一致：
      flight → 重排航班 / hotel → 换酒店 / budget → 重核预算 / 其余 → 重编行程
    """
    targets = {v.get("fix_by", "itinerary") for v in violations if isinstance(v, dict)}
    fix_map = {"flight": flight_agent, "hotel": hotel_agent, "budget": budget_agent}
    for key in ("flight", "hotel", "budget"):
        if key in targets:
            return fix_map[key]
    return itinerary_agent


# ——— 构建图 ———


def build_planner_graph():
    """构建并返回编译后的 LangGraph StateGraph

    图结构：
      profile → data_collection（内含 Flight∥Hotel∥POI 并行执行）
      → 按 strategies fan-out 到 process_strategy（每个策略独立走 Itinerary→Budget→Constraint）
      → process_strategy 结果自动合并到 plan_results（operator.add）
      → synthesizer → END
    """
    workflow = StateGraph(PlannerState)

    # 添加节点
    workflow.add_node("profile", _profile_node)
    workflow.add_node("direct_setup", _direct_setup_node)
    workflow.add_node("data_collection", _data_collection_node)
    workflow.add_node("process_strategy", _process_strategy_node)
    workflow.add_node("synthesizer", _synthesizer_node)

    # 入口
    workflow.set_entry_point("profile")

    # 条件路由：推荐 vs 直接
    workflow.add_conditional_edges(
        "profile",
        _route_after_profile,
        {"data_collection": "data_collection", "direct_setup": "direct_setup"},
    )
    workflow.add_edge("direct_setup", "data_collection")

    # 数据采集完成后 → 按策略分叉
    workflow.add_conditional_edges(
        "data_collection",
        _fan_out_strategies,
        path_map=None,  # Send list，每个 Send 指定目标节点
    )

    # process_strategy → Synthesizer
    workflow.add_edge("process_strategy", "synthesizer")

    # Synthesizer → END
    workflow.add_edge("synthesizer", END)

    return workflow.compile()
