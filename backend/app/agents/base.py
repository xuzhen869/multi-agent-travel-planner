"""Agent 基类 — 所有专业 Agent 的抽象接口

每个 Agent 遵循统一的生命周期：
  1. 接收结构化输入
  2. 调用 LLM + 工具
  3. 返回结构化输出
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Agent 抽象基类"""

    name: str = "base"
    description: str = ""

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """执行 agent 逻辑

        Args:
            state: LangGraph 共享状态字典

        Returns:
            更新后的状态字典（仅包含当前 agent 负责的键）
        """
        ...
