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
pytest backend/tests/test_pipeline.py -v

# E2E 测试（需要 .env 里有真实 DEEPSEEK_API_KEY）
pytest backend/tests/test_e2e.py -v -s

# 运行评估对比脚本（单 Agent vs 多 Agent，需要 API key）
python backend/evaluation/run_eval.py

# Schema 导入验证
python -c "from backend.app.schemas.agent import Outline, Script, ReviewResult; print('OK')"
python -c "from backend.app.pipeline.orchestator import init_state, run_pipeline; print('OK')"

# Docker 部署
docker-compose -f docker/docker-compose.yml up -d
```

## 项目概述

多 Agent 协作流水线，自动生成短视频口播脚本。面向 MCN 机构场景：用户输入选题+账号风格+目标时长，系统自动输出带节奏标记的完整口播稿。五层递进实现：跑通 → 评估 → 护栏 → 观测 → 部署。

**后端**: FastAPI + LangChain + DeepSeek + Pydantic | **前端**: Vue 3 + Vite | **搜索**: Tavily API | **编排**: 自定义状态机 (while + dict) | **可观测**: LangFuse (可选)

## 项目结构

```
项目根目录/
├── pyproject.toml              # Python 项目配置（依赖/构建/测试路径）
├── .env.example                # 环境变量模板，部署时复制为 .env 并填入真实 Key
├── .env                        # 实际环境变量（gitignore，不提交）
├── .gitignore
├── README.md                   # 对外说明文档（架构图/快速开始/API 表）
├── CLAUDE.md                   # 本文件
│
├── backend/                    # Python 后端
│   ├── __init__.py             # 包标识 + setuptools 发现标记
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI 入口 — 创建 app、挂 CORS、注册路由、/health
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py         # Depends 依赖注入 — get_pipeline() 返回 run_pipeline
│   │   │   └── router.py       # POST /generate + GET /health + _state_to_response()
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Agent 基类 — BaseAgent + _invoke() + extract_json()
│   │   │   ├── planning.py     # 策划 Agent — deepseek-reasoner + Tavily 搜热点 → Outline
│   │   │   ├── writing.py      # 写作 Agent — deepseek-chat + 三种风格指南 → Script
│   │   │   ├── review.py       # 审核 Agent — deepseek-reasoner + 四维评分 + Tavily 事实核查 → ReviewResult
│   │   │   └── revision.py     # 修改 Agent — deepseek-chat，只改 P0/P1，保留 P2 和原文风格 → Script
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py       # Settings 单例 — 从 .env 加载所有 API Key 和模型配置
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py        # Agent 间数据模型 — Section/Outline/Script/Issue/ReviewResult
│   │   │   ├── request.py      # API 请求体 — GenerateRequest/ConfirmRequest
│   │   │   └── response.py     # API 响应体 — StepInfo/GenerateResponse
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   └── orchestator.py  # 编排器 — run_pipeline() 状态机 + init_state() + _build_step_list()
│   │   ├── guardrails/
│   │   │   ├── __init__.py
│   │   │   └── compliance.py   # 合规检测 — 极限词/医疗断言/政治敏感正则 + format_check
│   │   └── tracker/
│   │       ├── __init__.py
│   │       └── langfuse.py     # LangFuse 追踪 — @trace_agent 装饰器（无 Key 时退化为 print）
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_pipeline.py    # 编排器单测（无需 API Key）— init_state + state 流转
│   │   └── test_e2e.py         # 端到端测试（需 API Key）— health/422/全流水线
│   └── evaluation/
│       ├── topics.json         # 评估数据集 — 10 个选题 × 3 种风格 = 30 个测试样本
│       └── run_eval.py         # 对比评估脚本 — 单 Agent vs 多 Agent 盲评打分
│
├── frontend/                   # Vue 3 前端 (Vite 构建)
│   ├── index.html              # HTML 入口 — 挂载点 <div id="app"> + Google Fonts 引入
│   ├── package.json            # Node 依赖 (vue/vite/@vitejs/plugin-vue)
│   ├── vite.config.js          # Vite 配置 — 端口 5173 + proxy 转发 /generate,/health → 8000
│   └── src/
│       ├── main.js             # Vue 应用入口 — createApp(App).mount('#app')
│       ├── App.vue             # 根组件 — 全局状态(appState/response/currentState) + autoContinue 接力
│       ├── api/
│       │   └── index.js        # API 封装 — generateScript() / confirmAction() / healthCheck()
│       └── components/
│           ├── InputForm.vue   # 输入表单 — 选题/风格/时长/auto_mode + 确认按钮组 + 反馈面板
│           ├── PipelineView.vue # 流水线进度 — 步骤指示器(idle/active/done) + skeleton + 大纲预览
│           └── ScriptOutput.vue # 脚本输出 — 脚本全文(节奏标记彩色高亮) + 评分/轮次/耗时 + issue 清单
│
├── docker/                     # Docker 容器化
│   ├── Dockerfile.api          # API 服务镜像 — Python 3.12 + pip install + uvicorn
│   └── docker-compose.yml      # 单服务编排（api 一个进程内跑完整流水线）
│
└── docs/                       # 项目文档
    ├── 项目6-自媒体口播脚本自动生成工厂.md        # 原始课程需求文档（业务场景 + 五层实现 + 每日任务）
    └── superpowers/specs/2026-05-17-自媒体口播脚本工厂-设计文档.md  # 完整设计文档
```

### 依赖关系（分层）

```
router.py  ──HTTP 调用──▶  orchestator.py  ──直接调用──▶  planning/writing/review/revision.py
    │                            │                              │
    ├── deps.py                  ├── _build_step_list()         └── base.py (BaseAgent + _invoke)
    ├── schemas/request.py       └── init_state()                   │
    └── schemas/response.py                                     └── extract_json()
            │
            └── schemas/agent.py  ←── Pydantic 模型被 agents 和 schemas 两边 import
```

每个文件只依赖它的下层，不存在循环引用。`schemas/agent.py` 是最底层的共享类型，被 agents、request、response 三层共用。

## 环境变量 (.env)

```bash
DEEPSEEK_API_KEY=sk-xxx          # 必填，DeepSeek 开放平台申请
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
TAVILY_API_KEY=tvly-xxx          # 可选，不填则跳过搜索，功能降级但不阻塞
LANGFUSE_PUBLIC_KEY=pk-lf-xxx    # 可选，不填则退化为 print 日志
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

`backend/app/core/config.py` 的 `Settings` 类通过 `pydantic_settings.BaseSettings` 自动从 .env 和环境变量加载。`get_settings()` 用 `@lru_cache()` 缓存单例。

## 架构：流水线状态机

### 步骤流转

```
plan → wait_confirm → write → review → revise → review → ... → done
                                 ↑_____________|  (最多 3 次 review↔revise 循环)
```

`run_pipeline()` 的核心设计：while 循环每次迭代只执行一个 step 就 break。一次 HTTP 请求只推进一步。这保证了前端能实时看到进度更新，而不是等 30-60 秒才拿到最终结果。

实际执行路径：
- **全自动 mode** (`auto_mode=true`): plan → write → review → (revise→review)×N → done
- **人工确认 mode** (`auto_mode=false`): plan → wait_confirm (暂停) → 等前端传回 confirm_action → write → ... → done

### state dict 完整字段

```python
state = {
    # 控制字段
    "step": "plan",              # plan | wait_confirm | write | review | revise | done
    "auto_mode": True,           # True=全自动一口气跑完, False=策划完暂停
    "confirm_action": "",        # continue | replan | revise_outline (二次调用时前端填入)
    "feedback": "",              # 用户对重策划/改大纲的文本要求

    # 输入参数
    "topic": "打工人如何保持精力",
    "style": "知识",             # 知识 | 搞笑 | 情感
    "duration": 120,             # 目标时长(秒)

    # Agent 产出（初始 None，Agent 执行后填充）
    "outline": None,             # 策划产出 → Outline.model_dump()
    "script": None,              # 写作/修改产出 → Script.model_dump()
    "review": None,              # 审核产出 → ReviewResult.model_dump()
    "revision_count": 0,         # 修改轮次计数

    # 终稿元信息（done 时填充）
    "final_script": None,
    "grade": "normal",           # normal(通过) | degraded(降级)
    "needs_human": False,        # 超限降级时为 True
    "unresolved_issues": [],     # 超限后仍未解决的 P0/P1 问题

    # 内部字段（_ 前缀，不暴露给前端）
    "_agents": {...},            # Agent 实例缓存 dict
    "_steps": [...],             # 步骤状态列表
    "_elapsed": 0,               # 累积耗时
}
```

### 跨请求状态保持

HTTP 无状态 + 流水线有状态 → 通过 state dict 在请求/响应间来回传解决。

1. 首次 POST /generate → 后端创建 state → 执行一步 → `_state_to_response()` 清理掉 `_agents` 等不可序列化字段 → 返回 `GenerateResponse.state`
2. 前端 `App.vue` 把 `state` 保存到 `currentState` 变量
3. 前端 `autoContinue()` 自动把 `currentState` 包进 `ConfirmRequest.state` 再次 POST /generate
4. 后端恢复 state → 读 `state["step"]` → 执行对应 Agent → 返回新 state
5. 直到 `step == "done"` 或 `step == "wait_confirm"` 停止

`_state_to_response()` 在 `backend/app/api/router.py:46`，它做了关键的清理工作：pop `_steps`、pop `_elapsed`、pop `_agents`，再把剩余业务字段打包成 `serializable_state` 塞进响应的 `state` 字段。

## API 接口

### POST /generate

同一个端点承载两种调用，靠 body 字段自动区分：

**首次调用**：
```json
{
  "topic": "打工人如何保持精力",
  "style": "知识",
  "duration": 120,
  "auto_mode": true
}
```

**确认调用**（auto_mode=false 时策划完成后）：
```json
{
  "confirm_action": "continue",
  "feedback": "",
  "state": { /* 上次响应里的完整 state */ }
}
```

`router.py` 用 `dict = Body(...)` 直接接收 raw JSON，然后手动判断 `"topic" in body` vs `"confirm_action" in body`。不用 `Union[GenerateRequest, ConfirmRequest]` 是因为 FastAPI 对 Body Union 支持不稳定。

### GET /health

```json
{"status": "ok", "service": "script-factory"}
```

### 响应结构 (GenerateResponse)

| 字段 | 类型 | 说明 |
|------|------|------|
| step | str | 当前步骤: plan / wait_confirm / write / review / revise / done |
| steps | StepInfo[] | 所有步骤状态 [{name, status: idle\|active\|done, label}, ...] |
| outline | dict\|null | 策划产出（标题/钩子/段落/金句） |
| script | dict\|null | 脚本内容（含 rhythm markers） |
| review | dict\|null | 审核结果（评分/问题列表） |
| revision_count | int | 修改次数 |
| grade | str | normal \| degraded |
| needs_human | bool | 是否需要人工处理未解决问题 |
| unresolved_issues | list | 超限后未解决的 P0/P1 问题 |
| elapsed_time | float | 累积耗时(秒) |
| state | dict | 完整干净 state，前端下次调用原样传回 |

## Agent 体系

### 四种 Agent 及其分工

| Agent | 文件 | 模型 | 职责 | 搜索 |
|-------|------|------|------|------|
| PlanningAgent | `agents/planning.py` | deepseek-reasoner | 分析选题 → 搜热点 → 输出 Outline (标题+钩子+段落+金句≥3) | Tavily 搜热点 |
| WritingAgent | `agents/writing.py` | deepseek-chat | 读大纲 → 按风格指南写口播稿 → 嵌入节奏标记 [快][慢][重音][停顿1s] | 无 |
| ReviewAgent | `agents/review.py` | deepseek-reasoner | 四维打分(信息量/口语化/合规性/可用率) → 输出 Issue 分级(P0/P1/P2) | Tavily 事实核查 |
| RevisionAgent | `agents/revision.py` | deepseek-chat | 读脚本+issues → 只改 P0/P1 问题 → 不动 P2 → 保留原文风格 | 无 |

模型选择逻辑：策划和审核需要分析推理，用 reasoner；写作和修改是执行型任务，用 chat 更快更省。

### BaseAgent 基类 (`agents/base.py`)

所有 Agent 继承此类，只需实现 `run(self, state: dict) -> dict`。

```python
class BaseAgent(ABC):
    def __init__(self, model_name=None):
        # ChatOpenAI 的 openai_api_base 指向 DeepSeek（兼容 OpenAI SDK）
        self.llm = ChatOpenAI(
            model=model_name or get_settings().deepseek_chat_model,
            openai_api_key=get_settings().deepseek_api_key,
            openai_api_base=get_settings().deepseek_base_url,
            temperature=0.7, max_tokens=4096,
        )

    @abstractmethod
    def run(self, state: dict) -> dict:
        """读 state → 调 LLM → 写回 state。Agent 不知道前一个是谁、后一个是谁。"""

    def _invoke(self, messages: list, schema: type, state: dict):
        """统一 LLM 调用流程: invoke → extract_json → schema(**data) → 返回 Pydantic 对象。
        解析失败返回 None，各 Agent 的 run() 自行兜底。"""
        response = self.llm.invoke(messages)
        data = extract_json(response.content)
        return schema(**data)
```

### 为什么不用 LangChain 模板 / structured output

三个踩坑记录：
1. **不用 ChatPromptTemplate / LangChain f-string 模板**：LangChain 模板引擎会对 `{}` 做二次解析，与 Python f-string 冲突，出 "Invalid format specifier" 错误。所有 Agent 改用 `SystemMessage(content=f"...")` 直接拼字符串。
2. **不用 PydanticOutputParser / with_structured_output**：DeepSeek 上这两个不稳定，有时不填内容而是回吐 JSON Schema 本身。改为 prompt 里写单行 JSON 示例 + `extract_json()` 手动解析。
3. **不用 LangGraph**：本项目的流程是线性的（唯一分支是 auto_mode 开关和审核结果判断），没有并行节点、不需要 checkpoint、不需要流式中间输出。`while` + `dict` 50 行搞定，LangGraph 会多引入 15+ 依赖和复杂图配置。

### extract_json(`base.py:34`)

从 LLM 文本响应中提取 JSON，处理 markdown 代码块包裹的常见情况：

```python
def extract_json(raw: str) -> dict:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())
```

### 每个 Agent 的 run() 通用模式

```python
def run(self, state):
    # 1. 从 state 读参数
    topic = state.get("topic", "")
    style = state.get("style", "知识")

    # 2. 拼 system prompt（Python f-string + JSON 格式示例）
    system = f"""你是...角色设定...
严格按JSON格式输出（不要输出其他内容）：
```json
{{"field1":"value","field2":123}}
```"""

    # 3. 调 LLM → 提取 JSON → 转 Pydantic
    messages = [SystemMessage(content=system), HumanMessage(content="...")]
    result = self._invoke(messages, OutPutSchema, state)

    # 4. 兜底处理
    if result is None:
        result = OutPutSchema(...)  # 默认值

    # 5. dump 回 state
    state["xxx"] = result.model_dump()
    return state
```

### 审核 → 修改循环的决策逻辑 (`orchestator.py:186`)

```python
must_fix = [i for i in issues if i.get("severity") in ("P0", "P1")]

if not must_fix:
    # 没有必改问题 → passed → 输出终稿
    state["final_script"] = script; state["grade"] = "normal"; state["step"] = "done"
elif revision_count >= 3:
    # 超过最大修改轮次 → 降级输出，标记人工处理
    state["final_script"] = script; state["unresolved_issues"] = must_fix
    state["needs_human"] = True; state["grade"] = "degraded"; state["step"] = "done"
else:
    state["step"] = "revise"  # 进入修改
```

## Pydantic Schema 层次 (`backend/app/schemas/`)

三层 Schema，对应数据流转的三个阶段：

1. **agent.py** — Agent 间消息格式：`Section → Outline`, `Script`, `Issue → ReviewResult`。Agent 产出直接用这些 Pydantic 模型，`model_dump()` 成 dict 写入 state。
2. **request.py** — API 入参：`GenerateRequest` (topic/style/duration/auto_mode), `ConfirmRequest` (confirm_action/feedback/state)。
3. **response.py** — API 出参：`StepInfo` (name/status/label), `GenerateResponse` (所有前端需要的字段 + 完整的 serializable state)。

Issue 严重级别：P0=合规/法律必改, P1=事实/数据必改, P2=风格建议仅记录。

## 护栏 (`guardrails/compliance.py`)

纯正则匹配，不依赖 LLM，保证 100% 拦截率：

- `FORBIDDEN_WORDS_PATTERN` — 广告法极限词（最好/第一/国家级/唯一/顶级/极致/绝对/永久/万能/首选/冠军/王牌/无敌/史上最强/世界第一/全国第一...）
- `MEDICAL_CLAIMS_PATTERN` — 医疗健康敏感断言（治愈/根治/神药/特效药/一针见效/药到病除/百分百有效/彻底消除/永不复发/祖传秘方/抗癌/降三高/排毒养颜）
- `POLITICAL_SENSITIVE` — 政治敏感词库（当前为空列表，仅预留入口）

`run_compliance_check(text: str) -> dict` 执行全部三项检测，返回 `{passed, issues, summary}`。

审核 Agent 的 prompt 层面还额外要求 LLM 做四维合规评分。两条路径互补：正则保证硬性拦截，LLM 捕捉语义层面的风险。

## 前端数据流

### 组件树与状态流转

```
App.vue (全局状态: appState ∈ {idle, running, confirming, done})
├── InputForm.vue    (左侧5列) — 表单输入 + 确认按钮组
├── PipelineView.vue (右侧7列) — 进度条 + skeleton 占位 + 大纲预览
└── ScriptOutput.vue (底部全宽) — 脚本全文(节奏标记高亮) + 元信息栏 + issue 列表
```

**appState 驱动 UI**：
- `idle` → InputForm 可用，PipelineView 灰色提示 "填写表单开始"
- `running` → InputForm disabled button "生成中..."，PipelineView 当前步骤蓝色脉冲 + skeleton 动画
- `confirming` → InputForm 展示三个确认按钮（确认大纲/重新策划/修改要求），PipelineView 展示大纲详情
- `done` → InputForm 恢复可用，PipelineView 全部绿色 done，ScriptOutput 展示完整结果

### 全自动模式的接力机制 (`App.vue:73`)

```javascript
// updateResponse 检测到中间步骤时自动发起下一次请求
function updateResponse(data) {
  Object.assign(response, data)
  currentState = data.state
  if (data.step === 'done') {
    appState.value = 'done'
  } else if (data.step === 'wait_confirm') {
    appState.value = 'confirming'
  } else {
    appState.value = 'running'
    autoContinue()  // ← 自动发 confirm 请求推进到下一步
  }
}
```

`autoContinue()` 打包 `confirm_action: 'continue'` + `state: currentState`，调 `confirmAction()` → POST /generate。后端收到后从 state["step"] 知道该执行哪一步。

### 设计系统

Swiss Modernism 2.0: 主色 `#2563EB`，点缀 `#F97316`（确认按钮/金句颜色），成功 `#059669`，危险 `#DC2626`。字体 Atkinson Hyperlegible。12 列 CSS Grid，768px 以下全部单列堆叠。

### ScriptOutput 的节奏标记渲染

口播脚本中嵌入的 `[快]` `[慢]` `[重音]` `[停顿1s]` 等标记被正则替换为带颜色背景的内联标签：
- `[快]` → 蓝底 `#DBEAFE` / 蓝字 `#1D4ED8`
- `[慢]` → 黄底 `#FEF3C7` / 棕字 `#B45309`
- `[重音]` → 红底 `#FEE2E2` / 红字 `#DC2626`
- `[停顿Ns]` → 紫底 `#E0E7FF` / 紫字 `#4338CA`

## 评估体系 (`backend/evaluation/`)

10 个选题 × 3 种风格（知识/搞笑/情感）= 30 个样本。每个样本跑两份：
- **单 Agent**：一个 `ChatPromptTemplate` 直接出完整脚本（无策划/审核/修改流程）
- **多 Agent**：走完整流水线

两份结果分别送审核 Agent 盲评打分，按风格分组算均值。评估脚本还记录每份的耗时和修改轮次。

## 可观测 (`tracker/langfuse.py`)

模块级开关：检查 `.env` 中是否有 LangFuse 的 public_key 和 secret_key，没有则全局退化为 `print` 日志。

`@trace_agent("name")` 装饰器记录：Agent 名称、耗时、当前 step、revision_count、异常信息。`_langfuse_enabled` 为 False 时装饰器只做 print 和计时，不影响任何功能。

`flush()` 确保数据发送完成，但当前未在任何地方调用（如果未来在生产中使用，需在 shutdown 事件或 finally 块中调用）。

## Docker 部署 (`docker/`)

```
docker-compose.yml
└── api  (端口 8000)
```

单服务架构：API + 全部 4 个 Agent + 编排器跑在同一个 Python 进程内。流水线是纯串行的（写作等策划、审核等写作），拆成独立微服务只会加网络延迟，没有收益。

`Dockerfile.api` 构建 API 服务，`docker-compose up -d` 启动端口 8000。

## 测试策略

`test_pipeline.py` — 无需 API key 的纯逻辑测试：测试 `init_state()` 默认值/自定义值、测试 state 流转逻辑（wait_confirm → continue / replan 后 step 和 confirm_action 是否正确）。

`test_e2e.py` — 需要真实 API key（通过 `pytest.mark.skipif` 条件跳过）：用 `httpx.AsyncClient` + `ASGITransport(app=app)` 做端到端测试。测试 health check 返回 200、测试空 topic 返回 422、测试完整流水线返回 done。

## 已知问题与注意事项

1. **LangFuse flush 未调用**：`tracker/langfuse.py` 的 `flush()` 函数未被任何地方调用，如果 LangFuse 有缓冲模式，关闭进程前可能丢失最后几条 trace。（生产环境建议在 FastAPI shutdown 事件中调用）
2. **搜索失败静默处理**：Tavily 搜索失败时返回 `""` 不抛异常，是刻意设计的降级策略（搜索只是辅助，不能阻塞主流程）。修改时注意保持此行为。
3. **test_e2e.py 的 skipif 条件**：不仅检查 key 是否存在，还检查是否为占位符（包含 `"your-deepseek-key"`），避免用占位符跑浪费调用的测试。
