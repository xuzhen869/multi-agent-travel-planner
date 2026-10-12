"""POI 搜索工具 — 百度地图地点检索 API（覆盖国内）"""

import json
import asyncio
from typing import Any

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.baidu_tools import place_search as baidu_place_search


class POISearchInput(BaseModel):
    """POI 搜索参数"""

    query: str = Field(description="搜索关键词，如 '外滩 景点' 或 '南京路 餐厅'")
    location: str | None = Field(
        default=None, description="中心经纬度，如 '35.6895,139.6917'（可选）"
    )
    region: str | None = Field(default=None, description="行政区划（城市名），如 '上海'")
    poi_type: str = Field(
        default="tourist_attraction",
        description="类型: tourist_attraction | restaurant | cafe | museum | park（百度侧以 query 关键词为准）",
    )
    max_results: int = Field(default=10, ge=1, le=20)


class POISearchTool(BaseTool):
    """搜索目的地景点/餐厅（百度）"""

    name: str = "search_poi"
    description: str = (
        "搜索目的地景点和餐厅，返回名称、评分、地址、坐标等信息。"
        "参数示例：query='外滩 景点', region='上海', max_results=10"
    )
    args_schema: type[BaseModel] = POISearchInput

    async def _arun(
        self,
        query: str,
        location: str | None = None,
        region: str | None = None,
        poi_type: str = "tourist_attraction",
        max_results: int = 10,
    ) -> str:
        # 优先使用 region（城市名）限定区域；百度按 query 关键词检索
        result = await baidu_place_search(query, region=region, max_results=max_results)
        return json.dumps(result, ensure_ascii=False)

    def _run(self, **kwargs: Any) -> str:
        return asyncio.run(self._arun(**kwargs))
