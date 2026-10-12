"""汇率换算工具 — Open Exchange Rates API"""

import json
import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings


class CurrencyInput(BaseModel):
    """汇率查询参数"""

    from_currency: str = Field(default="CNY", description="源货币代码，如 CNY")
    to_currency: str = Field(default="JPY", description="目标货币代码，如 JPY")
    amount: float = Field(default=1.0, description="金额")


class CurrencyTool(BaseTool):
    """实时汇率换算"""

    name: str = "exchange_currency"
    description: str = (
        "查询实时汇率并进行换算。参数示例：from_currency='CNY', to_currency='JPY', amount=10000"
    )
    args_schema: type[BaseModel] = CurrencyInput

    async def _arun(
        self, from_currency: str = "CNY", to_currency: str = "JPY", amount: float = 1.0
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://open.er-api.com/v6/latest/" + from_currency.upper(),
                )
                resp.raise_for_status()
                data = resp.json()

            rates = data.get("rates", {})
            rate = rates.get(to_currency.upper())

            if rate is None:
                return json.dumps({
                    "error": f"不支持的货币: {to_currency}",
                    "supported": list(rates.keys()),
                })

            result = round(amount * rate, 2)
            return json.dumps({
                "from": from_currency.upper(),
                "to": to_currency.upper(),
                "amount": amount,
                "result": result,
                "rate": round(rate, 6),
                "updated_at": data.get("time_last_update_utc", ""),
            })

        except httpx.HTTPError as e:
            return json.dumps({"error": f"汇率查询失败: {str(e)}"})
        except Exception as e:
            return json.dumps({"error": f"未知错误: {str(e)}"})

    def _run(self, **kwargs) -> str:
        import asyncio
        return asyncio.run(self._arun(**kwargs))
