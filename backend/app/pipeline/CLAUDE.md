# CLAUDE.md — pipeline

## 地图

```
orchestator.py    — run_pipeline() 状态机 + init_state() + _build_step_list()
```

**init_state(topic, style, duration, auto_mode) → dict**：创建初始 state，step="plan"，所有数据字段 None。

**_build_step_list(state) → list[dict]**：生成 4 步骤状态列表（策划/写作/审核/修改），根据 `state["step"]` 决定每个步骤是 idle/active/done/skipped。

**run_pipeline(state) → dict**：while 循环状态机，每次调用只执行一个 step 就 break，返回更新后的 state。step 流转：

```
plan → wait_confirm → write → review → revise → review → ... → done
                                 ↑_____________|  (最多 3 轮)
```

- `auto_mode=true`: plan → write → review → (revise→review)×N → done
- `auto_mode=false`: plan → wait_confirm → [等前端传 confirm_action] → write → ... → done

确认动作三种：`continue`（继续）、`replan`（清空大纲重新策划）、`revise_outline`（带 feedback 改大纲）。

## 规则

**1. 一次 HTTP 请求只推进一步。** 每个 step 执行后必须 `break`，不能连续执行多步。前端需要看到实时进度。

**2. 最多修改 3 轮。** `MAX_REVISIONS = 3`。超限后降级输出：`grade="degraded"`，`needs_human=True`，保留未解决的 P0/P1 到 `unresolved_issues`。

**3. 护栏有三处检查点。** 写作后（护栏①）、修改后（护栏②）执行 `run_compliance_check()`，结果存 `_compliance_issues`。审核阶段（护栏③）合并正则结果到 LLM 审核 issues，补上正则拦截的条目。

**4. `_agents` 不可序列化。** Agent 实例在 `_state_to_response()` 中被 pop 掉（router.py:78）。下次请求检测到 `_agents` 不在 state 中，自动重新创建。

**5. revision_count 只在 revise 步骤递增。** 避免 plan/write 阶段误计数。
