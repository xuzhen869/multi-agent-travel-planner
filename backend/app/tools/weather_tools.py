"""天气查询工具 — 百度地图天气 API（覆盖国内城市）"""

import json
import asyncio
from typing import Any

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.baidu_tools import weather as baidu_weather


class WeatherInput(BaseModel):
    """天气查询参数"""

    city: str = Field(description="城市名，如 '北京' 或 '东京'")
    date: str | None = Field(default=None, description="日期 YYYY-MM-DD（未来 5 天内）")


class WeatherTool(BaseTool):
    """查询目的地天气（百度，国内城市；境外/无 AK 时降级为空）"""

    name: str = "get_weather"
    description: str = (
        "查询目的地的天气预报，返回温度、天气状况、湿度等。"
        "参数示例：city='北京', date='2026-10-01'"
    )
    args_schema: type[BaseModel] = WeatherInput

    async def _arun(self, city: str, date: str | None = None) -> str:
        result = await baidu_weather(city, date)
        return json.dumps(result, ensure_ascii=False)

    def _run(self, **kwargs: Any) -> str:
        return asyncio.run(self._arun(**kwargs))
