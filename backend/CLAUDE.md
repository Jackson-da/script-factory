# CLAUDE.md — backend

后端专属指南。跨模块内容（架构、API、环境变量）见根目录 `CLAUDE.md`。

子目录指南：
- `app/agents/CLAUDE.md` — 4 个 Agent 的"三个不用"坑、extract_json、搜索降级
- `app/pipeline/CLAUDE.md` — 状态机流转、护栏检查点、最大修改轮次
- `tests/CLAUDE.md` — 哪些测试要 API key、skipif 写法、脱机跑法

## 地图

```
backend/
├── app/
│   ├── main.py                FastAPI 入口：CORS、路由挂载、lifespan
│   ├── api/                   HTTP 层：router.py(端点) + deps.py(注入)
│   ├── agents/                4 个 Agent：planning/writing/review/revision + base.py
│   ├── core/                  config.py(Settings 单例) + logging.py(日志系统)
│   ├── schemas/               agent.py(Agent 间) / request.py(入参) / response.py(出参)
│   ├── pipeline/              orchestrator.py(状态机核心)
│   ├── guardrails/            compliance.py(正则护栏：极限词/医疗断言/政治敏感)
│   └── tracker/               langfuse.py(LLM 追踪，无 Key 退化为 logging)
├── tests/                     5 个测试文件
└── evaluation/                评估数据集 + 单 vs 多 Agent 对比脚本
```

## Pydantic Schema 层次

三层 Schema，数据流转三个阶段：`agent.py`（Agent 间 `Section→Outline/Script/Issue→ReviewResult`）→ `request.py`（API 入参）→ `response.py`（API 出参）。Agent 产出用 `model_dump()` 写 state；API 层用 `model_validate()` 校验。

Issue 严重级别：**P0**=合规/法律必改，**P1**=事实/数据必改，**P2**=风格建议仅记录不改。

## 护栏

`compliance.py`：纯正则，不调 LLM，保证 100% 拦截。

- `FORBIDDEN_WORDS_PATTERN` — 广告法极限词（最好/第一/国家级/唯一/顶级/极致/绝对...）
- `MEDICAL_CLAIMS_PATTERN` — 医疗断言（治愈/根治/一针见效/永不复发/祖传秘方...）
- `POLITICAL_SENSITIVE` — 政治敏感词（预留空列表）

审核 Agent prompt 层额外做语义审查。正则 + LLM 两条路径互补。

## 可观测

### 日志

`core/logging.py` 的 `setup_logging()` 在 lifespan 启动时调用。控制台 ≥`LOG_LEVEL`（默认 INFO），文件全量 DEBUG 到 `logs/app.log`，午夜轮转保留 7 天。

### LangFuse

`tracker/langfuse.py`：检查 .env 中是否有 Key，没有则退化为 logging。`@trace_agent("name")` 装饰器记录 Agent 名称/耗时/token/step/revision_count/异常。`flush()` 在 lifespan shutdown 阶段调用。

## 已知问题

**日志轮转**：`logs/app.log` 午夜轮转，保留 7 天。日志量异常增大时检查 `LOG_LEVEL` 是否误设 DEBUG。
