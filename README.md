# 自媒体口播脚本自动生成工厂

[![Tests](https://github.com/Jackson-da/script-factory/actions/workflows/test.yml/badge.svg)](https://github.com/Jackson-da/script-factory/actions/workflows/test.yml)

多 Agent 协作流水线，输入选题 + 风格 + 时长，自动输出带节奏标记的口播脚本。面向 MCN 机构场景：策划→写作→审核→修改，全自动闭环。

## 项目亮点

- **多 Agent 协作** — 4 个 Agent 各司其职（策划/写作/审核/修改），审核不通过自动循环修改，最多 3 轮
- **自研状态机替代 LangGraph** — 评估后认定线性流程不需要图编排，50 行 `while + dict` 搞定，少引入 15 个依赖
- **双护栏机制** — 正则硬拦截（极限词/医疗断言/政治敏感 100% 命中率）+ LLM 语义审查，审核评分 90 分通过阈值 + 各维度 ≥20 分保障
- **全栈可运行** — FastAPI + Vue 3，前端实时展示流水线进度，节奏标记彩色高亮
- **可观测** — LangFuse 全链路追踪 + logging 日志系统（控制台+文件双输出，按天轮转），16 处日志点全覆盖

## 评估数据

30 个样本（10 选题 × 3 风格），单 Agent vs 多 Agent 盲评对比：

| | 单 Agent | 多 Agent | 提升 |
|------|---------|---------|------|
| 总平均分 | 87.3 | 88.3 | +1.0 |
| 知识风格 | 87.5 | 88.4 | +0.9 |
| 搞笑风格 | 87.5 | 89.1 | **+1.6** |
| 情感风格 | 86.9 | 87.5 | +0.6 |
| 通过率 | — | **100%** | — |

多 Agent 在搞笑风格上提升最显著（+1.6 分），审核→修改循环对幽默内容的合规拦截和节奏优化效果明显。

## 架构

```
POST /generate
      │
      ▼
┌──────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ 策划 Agent    │ ──▶ │ 写作 Agent │ ──▶ │ 审核 Agent │ ──▶ │ 修改 Agent │
│ reasoner+Tavily│     │ chat+风格  │     │ reasoner   │     │ chat      │
└──────────────┘     └──────────┘     └──────────┘     └──────────┘
      │                    │                │                 │
      │              ┌─────┴─────┐    ┌────┴────┐     ┌─────┴──────┐
      ▼              │ 护栏①     │    │ 护栏③  │     │ 护栏②     │
  大纲+标题+金句     │ 正则检测  │    │ 合并    │     │ 正则检测   │
                     └───────────┘    └─────────┘     └────────────┘
                                                         │
                                              ┌──────────┴──────────┐
                                              │ 通过/no P0P1 → done │
                                              │ 不通过 → 修改(≤3轮) │
                                              │ 超限 → 降级+人工    │
                                              └─────────────────────┘
```

**HTTP 一次推一步**：前后端通过 state dict 在请求/响应间传递流水线状态。前端 `autoContinue()` 自动接力，直到 `done`。用户看到每一步实时进度，而不是等 60 秒才出结果。

## 技术栈

| 层 | 选型 | 说明 |
|------|------|------|
| 后端框架 | FastAPI | 异步支持，自带 OpenAPI 文档 |
| LLM 调用 | LangChain + DeepSeek | OpenAI 兼容协议，reasoner 用于分析、chat 用于生成 |
| 数据校验 | Pydantic v2 | Agent 间消息格式、API 请求/响应 |
| 前端 | Vue 3 + Vite | Composition API，CSS Grid 12 列响应式 |
| 搜索 | Tavily API | 策划时搜热点，审核时事实核查 |
| 日志 | logging | 控制台(INFO+) + 文件(DEBUG+, 按天轮转保留7天)，`LOG_LEVEL` 环境变量控制 |
| 可观测 | LangFuse | Agent 级耗时/token 追踪（无 Key 时退化为 logging 输出） |
| 编排 | 自定义状态机 | `while + dict`，不用 LangGraph |
| 部署 | Docker Compose | Nginx 反代统一入口，多容器协作（前端 Nginx + 后端 FastAPI） |

## 快速开始

### 1. 环境

```bash
# Python 3.12+, Node 18+
python -m venv .venv
.venv\Scripts\activate
pip install -e .
npm --prefix frontend install
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，必填 `DEEPSEEK_API_KEY`，Tavily 和 LangFuse 可选（不填自动降级）：

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
TAVILY_API_KEY=tvly-xxx          # 可选
LANGFUSE_PUBLIC_KEY=pk-lf-xxx    # 可选
LOG_LEVEL=INFO                   # 可选：DEBUG|INFO|WARNING|ERROR
```

### 3. 启动

```bash
# 后端（端口 8000）
uvicorn backend.app.main:app --reload

# 前端（端口 5173，Vite proxy → 8000）
npm --prefix frontend run dev
```

浏览器打开 `http://localhost:5173`，填选题 → 选风格 → 点生成。

**日志**：控制台显示 INFO 级别及以上，文件 `logs/app.log` 留存完整 DEBUG 记录。排查问题时设 `LOG_LEVEL=DEBUG` 查看完整调用链。

### 4. Docker 部署

```bash
# 在项目根目录执行（Windows 遇 gRPC 报错先执行 export DOCKER_BUILDKIT=0）
docker compose -f docker/docker-compose.yml up -d --build

# 多容器扩展：启动 3 个后端实例，Nginx upstream 自动轮询负载均衡
docker compose -f docker/docker-compose.yml up -d --scale backend=3

# 停止
docker compose -f docker/docker-compose.yml down
```

部署后访问 `http://服务器IP`，Nginx 在 80 端口统一接收请求：

| 请求路径 | 处理方式 |
|---------|---------|
| `/` | Nginx 返回前端页面（Vue SPA） |
| `/generate` | Nginx 转发到 upstream backends（负载均衡轮询） |
| `/health` | Nginx 转发到 upstream backends |

```
用户 → Nginx(:80) ──→ 前端静态文件
                 └──→ upstream backends ──→ backend-1 (:8000)
                                        ├──→ backend-2 (:8000)
                                        └──→ backend-3 (:8000)
                                        [均不暴露公网]
```

**安全设计**：后端端口不对外暴露，Nginx 是唯一公网入口。日志挂载到宿主机 `logs/` 目录，容器重启不丢失。

**负载均衡**：nginx.conf 中 `upstream backends` 声明后端名单，Docker DNS 自动解析 `backend` 为所有健康容器的内网 IP。Nginx 默认轮询分发请求。单容器时名单就一个，多容器时自动轮询，无需改配置。

**Windows 已知问题**：Docker Desktop 的 BuildKit（新一代构建引擎）通过 gRPC 与守护进程通信，WSL2 网络偶发断开导致构建失败。临时解决：`export DOCKER_BUILDKIT=0` 切换旧引擎。永久解决：Docker Desktop Settings → Docker Engine → 添加 `"features": {"buildkit": false}`。

## 测试

```bash
# 全量测试（97 个，无需 API Key 的纯逻辑测试可脱机跑）
pytest backend/tests/ -v

# E2E 测试（需要真实 API Key）
pytest backend/tests/test_e2e.py -v -s

# 评估对比（需要 API Key，30 样本约 30 分钟）
python backend/evaluation/run_eval.py
```

| 文件 | 数量 | 内容 |
|------|------|------|
| `test_pipeline.py` | 27 | 编排器状态机、步骤流转、兜底逻辑 |
| `test_compliance.py` | 34 | 极限词/医疗断言/政治敏感/格式校验 |
| `test_agents.py` | 21 | 4 个 Agent mock 测试、兜底、搜索调用 |
| `test_extract_json.py` | 12 | JSON 解析：代码块/嵌套/异常 |
| `test_e2e.py` | 3 | 端到端：health/422/完整流水线 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 首次调用传 topic/style/duration；后续传 confirm_action + state |
| GET | `/health` | `{"status": "ok"}` |

### 请求示例

**首次调用（全自动模式）**：
```json
{
  "topic": "打工人如何保持精力",
  "style": "知识",
  "duration": 120,
  "auto_mode": true
}
```

**确认调用（人工确认模式，策划完成后）**：
```json
{
  "confirm_action": "continue",
  "feedback": "",
  "state": { /* 上次响应返回的 state */ }
}
```

## 关键设计决策

**为什么不用 LangGraph？** 流水线是纯线性的（唯一分支是 auto_mode 开关和审核结果判断）。没有并行节点、不需要 checkpoint、不需要流式输出。`while + dict` 够用，LangGraph 会多 15+ 依赖和复杂图配置。

**为什么不用 LangChain 模板？** LangChain 的 f-string 模板解析器对 `{}` 做二次解析，与 Python f-string 冲突（`Invalid format specifier`）。所有 Agent 直接用 `SystemMessage(content=f"...")` 拼 prompt。

**为什么不用 PydanticOutputParser？** DeepSeek 上不稳定，有时不填内容而是回吐 JSON Schema 本身。改为 prompt 里写单行 JSON 示例 + `extract_json()` 手动解析。

**为什么搜索失败不抛异常？** Tavily 搜索是辅助功能（热点搜集、事实核查），失败时返回空字符串不阻塞主流程。刻意设计的降级策略。

**为什么前后端通过 dict 传状态？** HTTP 本身无状态，但流水线有状态。每个请求在后端恢复 state → 执行一步 → 序列化干净 state 返回前端。前端下次请求原样传回。简单直接，不需要 Redis/Session。

## 项目结构

```
├── backend/app/
│   ├── agents/          # 4 个 Agent（planning/writing/review/revision）
│   ├── api/             # router.py + deps.py
│   ├── core/            # config.py（Settings）+ logging.py（日志系统）
│   ├── schemas/         # Pydantic 模型（agent/request/response）
│   ├── pipeline/        # orchestrator.py（状态机核心）
│   ├── guardrails/      # compliance.py（正则护栏）
│   └── tracker/         # langfuse.py（可观测）
├── backend/tests/       # 97 个测试
├── backend/evaluation/  # 评估数据集 + 对比脚本
├── frontend/src/        # Vue 3 组件 + API 封装
├── docker/              # Docker Compose 多容器部署
│   ├── docker-compose.yml       # 服务编排（backend + frontend）
│   ├── Dockerfile.backend       # 后端镜像
│   ├── Dockerfile.frontend      # 前端多阶段构建
│   └── nginx.conf               # Nginx 反代 + SPA 路由 + upstream 负载均衡
├── .dockerignore         # Docker 构建排除规则
└── docs/                # 设计文档 + 实施计划
```
