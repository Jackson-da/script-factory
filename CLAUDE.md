# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 虚拟环境 + 依赖（Python 3.12+, Node 18+）
.venv\Scripts\activate && pip install -e .
npm --prefix frontend install

# 后端开发（端口 8000）
uvicorn backend.app.main:app --reload

# 前端开发（端口 5173，Vite proxy 自动转发 /generate /health 到 8000）
npm --prefix frontend run dev

# 测试（不调 API key 的纯逻辑测试）
pytest backend/tests/ -v

# E2E 测试（需要 .env 里有真实 DEEPSEEK_API_KEY）
pytest backend/tests/test_e2e.py -v -s

# 运行评估对比脚本（单 Agent vs 多 Agent，需要 API key）
python backend/evaluation/run_eval.py

# Schema 导入验证
python -c "from backend.app.schemas.agent import Outline, Script, ReviewResult; print('OK')"
python -c "from backend.app.pipeline.orchestator import init_state, run_pipeline; print('OK')"

# Docker 部署（前端 Nginx:80 + 后端 FastAPI:8000，Nginx 反代统一入口）
docker compose -f docker/docker-compose.yml up -d --build
```

## 项目概述

多 Agent 协作流水线，自动生成短视频口播脚本。面向 MCN 机构场景：用户输入选题+账号风格+目标时长，系统自动输出带节奏标记的完整口播稿。

**后端**: FastAPI + LangChain + DeepSeek + Pydantic | **前端**: Vue 3 + Vite | **编排**: 自定义状态机 (while + dict) | **搜索**: Tavily API | **可观测**: LangFuse + logging

## 架构

### 流水线步骤流转

```
plan → wait_confirm → write → review → revise → review → ... → done
                                 ↑_____________|  (最多 3 轮 review↔revise)
```

一次 HTTP 请求只推进一步，前端实时看到进度。`run_pipeline()` 的核心：while 循环每次迭代执行一个 step 就 break。

- **全自动** (`auto_mode=true`): plan → write → review → (revise→review)×N → done
- **人工确认** (`auto_mode=false`): plan → wait_confirm → 前端传回 confirm_action → write → ... → done

### state dict

流水线的唯一数据载体。关键字段：

```python
state = {
    "step": "plan",          # plan|wait_confirm|write|review|revise|done
    "auto_mode": True,       # True=全自动, False=策划后暂停等确认
    "confirm_action": "",    # continue|replan|revise_outline（前端填入）
    "feedback": "",          # 用户补充要求
    "topic": "...",          # 选题
    "style": "知识",         # 知识|搞笑|情感
    "duration": 120,         # 目标时长(秒)
    "outline": None,         # 策划产出
    "script": None,          # 写作/修改产出
    "review": None,          # 审核产出
    "revision_count": 0,     # 修改轮次
    "final_script": None,    # 终稿
    "grade": "normal",       # normal|degraded
    "needs_human": False,    # 超限降级为 True
    "unresolved_issues": [], # 超限未解决的 P0/P1
    "_agents": {...},        # 内部：Agent 实例缓存（不暴露前端）
    "_steps": [...],         # 内部：步骤状态列表
    "_elapsed": 0,           # 内部：累积耗时
}
```

### 跨请求状态保持

HTTP 无状态 + 流水线有状态 → state dict 在请求/响应间来回传：

1. POST /generate（首次） → 后端创建 state → 执行一步 → `_state_to_response()` 清理 `_agents` 等 → 返回 `GenerateResponse.state`
2. 前端 `App.vue` 保存 `currentState`
3. 前端 `autoContinue()` 自动打包 `{confirm_action, state}` 再次 POST /generate
4. 后端恢复 state → 执行下一步 → 返回新 state
5. 直到 `step == "done"` 或 `step == "wait_confirm"` 停止

## 项目结构

```
根目录/
├── pyproject.toml              # Python 依赖/构建/测试配置
├── .env.example                # 环境变量模板
├── CLAUDE.md                   # 本文件（跨模块通用内容）
│
├── backend/                    # Python 后端 → backend/CLAUDE.md
│   ├── app/
│   │   ├── main.py             # FastAPI 入口：CORS、路由注册、/health
│   │   ├── api/                # HTTP 层：router.py(端点) + deps.py(注入)
│   │   ├── agents/             # 4 个 Agent：planning/writing/review/revision
│   │   ├── core/               # config.py(Settings) + logging.py(日志)
│   │   ├── schemas/            # Pydantic：agent/request/response 三层
│   │   ├── pipeline/           # orchestrator.py(状态机核心)
│   │   ├── guardrails/         # compliance.py(正则护栏)
│   │   └── tracker/            # langfuse.py(LLM 追踪)
│   ├── tests/                  # test_pipeline/test_compliance/test_agents/test_e2e
│   └── evaluation/             # 评估数据集 + 对比脚本
│
├── frontend/                   # Vue 3 前端 → frontend/CLAUDE.md
│   └── src/
│       ├── App.vue             # 根组件：全局状态 + autoContinue 接力
│       ├── api/index.js        # API 封装
│       └── components/         # InputForm/PipelineView/ScriptOutput
│
├── docker/                     # Docker Compose 部署（多容器）
│   ├── docker-compose.yml      #   服务编排：backend + frontend
│   ├── Dockerfile.backend      #   后端镜像（Python 3.12-slim）
│   ├── Dockerfile.frontend     #   前端镜像（多阶段：Node构建→Nginx运行）
│   ├── nginx.conf              #   Nginx 反代配置（SPA路由+API转发）
│   └── .dockerignore           #   构建排除规则
├── docs/                       # 需求文档 + 设计文档
```

### 依赖方向

```
router.py → orchestrator.py → planning/writing/review/revision.py → base.py
    │              │
    └── schemas/ ──┘  ← Pydantic 模型被两边共用
```

每层只依赖下层，无循环引用。`schemas/agent.py` 是共享类型基础。

## 环境变量

```bash
DEEPSEEK_API_KEY=sk-xxx          # 必填
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
TAVILY_API_KEY=tvly-xxx          # 可选，不填跳过搜索
TAVILY_INCLUDE_DOMAINS=...       # 可选，限定搜索域名（逗号分隔，默认19个中文平台）
LANGFUSE_PUBLIC_KEY=pk-lf-xxx    # 可选，不填退化为 logging
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
LOG_LEVEL=INFO                   # DEBUG|INFO|WARNING|ERROR
```

`backend/app/core/config.py` 的 `Settings` 通过 `pydantic_settings.BaseSettings` 自动加载。

## API

### POST /generate

同一个端点两种调用，靠 body 字段区分：

**首次调用**：
```json
{"topic": "打工人如何保持精力", "style": "知识", "duration": 120, "auto_mode": true}
```

**确认调用**（auto_mode=false 或流水线中间步骤）：
```json
{"confirm_action": "continue", "feedback": "", "state": {/*上次返回的 state*/}}
```

### GET /health

```json
{"status": "ok", "service": "script-factory"}
```

### 响应关键字段

| 字段 | 说明 |
|------|------|
| step | plan/wait_confirm/write/review/revise/done |
| steps | 所有步骤 [{name, status:idle\|active\|done, label}] |
| hotspot | 策划阶段搜索的热点参考 [{title, content, url}] |
| outline/script/review | Agent 产出，初始 null |
| grade | normal(通过) / degraded(超限降级) |
| needs_human | 超限后需人工处理 |
| state | 干净 state dict，前端下次原样传回 |

## 子目录指南

- **后端细节**（Agent 体系、护栏、日志、测试、Docker、已知问题）→ `backend/CLAUDE.md`
- **前端细节**（组件树、状态流转、设计系统、节奏标记渲染）→ `frontend/CLAUDE.md`
