"""LLM 统一工厂 — 支持 DeepSeek / Anthropic 供应商切换。

所有 Agent 通过 get_llm() 获取实例，避免每个 Agent 各自绑定供应商实现。
切换供应商只需改配置 LLM_PROVIDER，无需改动任何 Agent 代码。

当所选供应商的 API Key 未配置时，get_llm() 返回降级占位实例：
调用时抛出清晰错误 → 触发各 Agent 已有的规则兜底逻辑，
保证整个规划流程在无 LLM 凭据时仍能产出基础结果。
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


class _UnavailableLLM:
    """LLM 未配置时的占位实现：ainvoke 即抛清晰错误。

    各 Agent 对 LLM 调用异常已有兜底（规则引擎 / fallback 策略），
    因此这里无需真正的模型也能保证流程可用。
    """

    def __init__(self, provider: str):
        self.provider = provider

    async def ainvoke(self, *_args, **_kwargs):
        raise RuntimeError(
            f"LLM 未配置：请为供应商 {self.provider} 配置 API Key"
            f"（当前 LLM_PROVIDER={self.provider}）。系统已降级为规则兜底生成基础结果。"
        )


def get_llm(temperature: float = 0.3, max_tokens: int = 4096, **kwargs):
    """按配置创建 LLM 实例（或未配置时的降级占位）。

    Args:
        temperature: 采样温度
        max_tokens: 最大输出 token
        **kwargs: 透传给具体实现的额外参数

    Returns:
        可调用的 Chat 模型实例（ainvoke(messages) -> AIMessage）
    """
    provider = settings.LLM_PROVIDER.strip().lower()

    if provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            logger.warning("DEEPSEEK_API_KEY 未配置，使用降级 LLM（规则兜底）")
            return _UnavailableLLM("deepseek")
        # DeepSeek 提供 OpenAI 兼容 API
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    # 默认 Anthropic
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY 未配置，使用降级 LLM（规则兜底）")
        return _UnavailableLLM("anthropic")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.LLM_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
