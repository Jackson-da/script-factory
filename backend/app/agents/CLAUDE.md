# CLAUDE.md — agents

## 地图

```
base.py          — BaseAgent 基类 + extract_json()
planning.py      — PlanningAgent: deepseek-reasoner + Tavily 搜热点 → Outline
writing.py       — WritingAgent:  deepseek-chat + 三种风格指南 → Script
review.py        — ReviewAgent:   deepseek-reasoner + 四维评分 + Tavily 事实核查 → ReviewResult
revision.py      — RevisionAgent: deepseek-chat，只改 P0/P1，不动 P2，保留原文风格
```

模型选择：策划和审核用 reasoner（需分析推理）；写作和修改用 chat（执行型任务，更快更省）。

每个 Agent 继承 `BaseAgent`，只实现 `run(self, state: dict) -> dict`。从 state 读数据 → 拼 prompt → 调 LLM → `model_dump()` 写回 state。Agent 不知道前一个是谁、后一个是谁。

`_invoke()` 统一调用流程：`llm.invoke(messages)` → `extract_json(raw)` → `schema(**data)` → 返回 Pydantic 对象。解析失败返回 None。

`extract_json()` 处理 LLM 把 JSON 包在 markdown 代码块的情况（```` ```json ``` ```` 或 ```` ``` ````）。

## 规则

**1. 不用 ChatPromptTemplate。** LangChain 对 `{}` 二次解析，与 Python f-string 冲突。直接用 `SystemMessage(content=f"...")` 拼字符串。

**2. 不用 PydanticOutputParser / with_structured_output。** DeepSeek 上不稳定，有时回吐 JSON Schema 本身而不是内容。做法：prompt 里写单行 JSON 示例 + `extract_json()` 手动解析。

**3. 不用 LangGraph。** 流水线是纯线性的。50 行 `while + dict` 够用，LangGraph 多 15+ 依赖。

**4. `_invoke()` 返回 None 必须兜底。** JSON 解析失败时 _invoke 返回 None，各 Agent 的 run() 必须构造默认 Pydantic 对象，不能让 None 往下传。

**5. Tavily 搜索失败不能抛异常。** 返回 `""`，打 `logger.warning()`。搜索是辅助功能，阻塞主流程会导致整个生成失败。
