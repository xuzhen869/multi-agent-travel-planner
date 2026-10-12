# 旅行规划多智能体协作平台

> 用一张 7 个 Agent 的有向图，解决航班、酒店、行程互相冲突的编排难题。

传统行程规划工具的失败点不在"单个环节查不到数据"，而在**多维度约束互相打架**：便宜的航班落地太晚、选中的酒店离 POI 太远、总预算算下来超支。人工协调这些冲突极其耗时，而单次 LLM 调用既算不准账，也发现不了冲突。

本项目把规划拆成一条**可回退的多智能体有向图**：并行采集 → 预算核算 → 约束校验 → 冲突回退修复 → 多方案合成。

---

## 核心能力

| 机制 | 说明 |
|---|---|
| 7-Agent 有向图 | LangGraph `StateGraph` 建模：Profile → (Flight ∥ Hotel ∥ POI) → Budget → Constraint → Synthesizer |
| 策略级并行 | `Send API` 动态分片，`operator.add` reducer 自动合并并行分支结果（map-reduce 模式） |
| 冲突自动修复 | `ConstraintAgent` 校验后按 `fix_by` 协议**回退路由**到对应 Agent 重跑，最多 3 轮 |
| 多方案输出 | Synthesizer 并行生成 3 套方案供对比择优 |
| 真实工具层 | 7 个 Agent 均封装 LLM 与真实工具：天气 / 汇率 / 地图 / 航班 / 酒店 / POI |
| 异步执行 | Celery + Redis 承载长任务，前端不阻塞 |
| 实时进度 | SSE 推送每个节点的执行状态，用户能看到规划进行到哪一步 |
| 账号体系 | JWT 双 Token + OAuth（Google / GitHub） |

**实测**：单次完整规划（Profile → 并行采集 → 3 方案并行 → Synthesizer）约 **58 秒**，约束冲突支持最多 3 轮自动回退修复。

---

## 编排图

```
                         ┌─────────────┐
                         │   Profile   │  解析用户偏好与硬约束
                         └──────┬──────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │   Flight   │   │   Hotel    │   │    POI     │   ← Send API 并行分片
       └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
             └────────────────┼────────────────┘
                              ▼   operator.add 自动合并
                        ┌───────────┐
                        │  Budget   │  预算核算
                        └─────┬─────┘
                              ▼
                        ┌───────────┐
                        │ Constraint│  冲突校验
                        └─────┬─────┘
                              │ fix_by 协议
              ┌───────────────┴───────────────┐
              │  发现冲突 → 回退到对应 Agent    │  最多 3 轮
              └───────────────┬───────────────┘
                              ▼
                        ┌───────────┐
                        │Synthesizer│  3 套方案并行合成
                        └───────────┘
```

---

## 技术栈

**后端**
- Python / FastAPI + Uvicorn
- SQLAlchemy 2.0（async）+ Alembic 迁移
- Pydantic v2（校验与 schema）
- python-jose（JWT）+ OAuth2（Google / GitHub）

**Agent 编排**
- LangGraph（`StateGraph` / `Send` API / Checkpoint）
- 自定义 reducer（`operator.add`）实现并行分支合并
- LLM：DeepSeek（OpenAI 兼容协议）/ Anthropic，可切换

**异步与实时**
- Celery + Redis：长任务队列
- SSE（Server-Sent Events）：规划进度实时推送

**工具层**
- 百度地图：POI 检索 / 地理编码 / 路线规划 / 天气
- 航班、酒店、汇率查询工具（未配置密钥时自动降级为规则兜底）

**前端**
- Next.js（App Router）+ TypeScript
- Tailwind CSS
- 自研 `useSSE` hook 消费进度流
- 组件：`AgentPipeline`（Agent 执行流水线可视化）/ `CinemaHome` / `PlanProgressCard`

**部署**
- Docker Compose：PostgreSQL + Redis + backend + frontend

---

## 快速开始

### Docker Compose（推荐，自带 Postgres + Redis）

```bash
cp backend/.env.example backend/.env
# 至少填入 DEEPSEEK_API_KEY 与 BAIDU_MAP_AK
docker compose up -d
```

- 前端：`http://localhost:3000`
- 后端 API 文档：`http://localhost:8000/docs`

### 本地开发

```bash
# 1. 后端
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 填入 DEEPSEEK_API_KEY / BAIDU_MAP_AK
alembic upgrade head
uvicorn app.main:app --reload                        # http://localhost:8000

# 2. Redis（Windows 可使用项目内置的 redis-windows，或自行安装）
redis-server

# 3. Celery Worker（另开终端）
cd backend && celery -A app.tasks.celery_app worker -l info --pool=solo

# 4. 前端
cd frontend
npm install
cp .env.local.example .env.local 2>/dev/null || echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev                                          # http://localhost:3000
```

---

## 目录结构

```
backend/app/
├── agents/                  # 多智能体编排
│   ├── graph.py             # StateGraph 定义：节点、边、条件路由
│   ├── base.py              # Agent 基类
│   ├── profile_agent.py     # 偏好与硬约束解析
│   ├── flight_agent.py      # ┐
│   ├── hotel_agent.py       # ├ 并行采集分支
│   ├── poi_agent.py         # ┘
│   ├── budget_agent.py      # 预算核算
│   ├── constraint_agent.py  # 冲突校验 + fix_by 回退决策
│   ├── itinerary_agent.py   # 逐日行程编排
│   └── synthesizer.py       # 多方案合成
├── api/                     # auth / users / trips / lookup / oauth
├── core/                    # database / redis / llm / geocode / security / exceptions
├── models/  schemas/        # ORM 与 Pydantic 模型
├── services/                # auth / planner / progress
├── tasks/                   # celery_app / planner_task
├── tools/                   # baidu / flight / hotel / poi / weather / currency
└── main.py

frontend/src/
├── app/                     # Next.js App Router
│   ├── planner/             # 规划入口
│   └── trips/[id]/          # 行程详情 / 进度 / 方案选择
├── components/
│   ├── cinema/AgentPipeline.tsx   # Agent 执行流水线可视化
│   └── trips/PlanProgressCard.tsx
└── hooks/useSSE.ts          # SSE 进度订阅

alembic/                     # 数据库迁移
docker-compose.yml           # Postgres + Redis + backend + frontend
```

---

## 配置

见 `backend/.env.example`。关键项：

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` / `LLM_PROVIDER` | LLM 供应商与密钥，支持 `deepseek` / `anthropic` 切换 |
| `BAIDU_MAP_AK` | 百度地图 AK，覆盖天气 / POI / 地址搜索 / 路线规划 |
| `DATABASE_URL` | 本地默认 SQLite，Docker 部署用 Postgres |
| `REDIS_URL` | Celery broker 与结果后端 |
| `JWT_SECRET` | **生产必须更换** |
| `GOOGLE_CLIENT_ID` / `GITHUB_CLIENT_ID` | 可选，OAuth 登录 |

> 仓库不含任何真实密钥，`.env` 已被 `.gitignore` 排除。

---

## 关键设计决策

**为什么用有向图而不是一条线性 Chain？**
线性 Chain 一旦某个环节的数据不满足约束（比如航班落地时间晚于酒店入住），只能从头重跑或直接把坏结果交给用户。有向图允许**局部回退**——只重跑出问题的那一个分支，其余分支的结果直接复用。

**为什么约束校验要独立成一个 Agent？**
把"校验"和"生成"混在同一个 LLM 调用里，模型会倾向于自我说服（生成什么就认为什么合理）。拆出来之后，`ConstraintAgent` 以对立视角检查预算、时间窗、地理距离，发现问题后通过 `fix_by` 协议明确指出应该回退到哪个 Agent、携带什么修正参数。

**为什么并行分支用 Send API 而不是固定边？**
航班、酒店、POI 的采集数量取决于用户输入的行程天数和目的地数量，是运行时才确定的。`Send` API 支持动态决定分片数量，配合 `operator.add` reducer 自动合并，无需为每种情况预先定义图结构。

**为什么长任务放 Celery 而不是 FastAPI 后台任务？**
一次完整规划约 58 秒，远超 HTTP 合理等待时间，且需要跨请求保持状态与重试。Celery + Redis 提供可靠的队列、重试与结果持久化，前端通过 SSE 订阅进度而不是长轮询。

---

## License

仅用于学习与交流。
