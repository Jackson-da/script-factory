# CLAUDE.md — components

## 地图

```
InputForm.vue     — 输入表单（选题/风格/时长/auto_mode）+ 确认按钮组（确认大纲/重新策划/修改要求）+ 反馈面板
PipelineView.vue  — 流水线进度（步骤指示器 idle/active/done/skipped）+ skeleton 占位 + 大纲预览
ScriptOutput.vue  — 脚本全文（节奏标记彩色高亮）+ 元信息栏（评分/轮次/状态/耗时）+ issue 列表
```

所有组件通过 props 接收数据，不直接调 API。API 调用在 `App.vue` 中统一管理，通过 `src/api/index.js` 的 `generateScript()` 和 `confirmAction()` 发请求。

## 规则

**1. 节奏标记颜色映射。** `ScriptOutput.vue` 的 `MARKER_STYLES` 是口播脚本的核心视觉规则，不要随意改：

| 标记 | 底色 | 字色 |
|------|------|------|
| `[快]` | `#DBEAFE` | `#1D4ED8` |
| `[慢]` | `#FEF3C7` | `#B45309` |
| `[重音]` | `#FEE2E2` | `#DC2626` |
| `[停顿Ns]` | `#E0E7FF` | `#4338CA` |

**2. appState 四态流转。** `App.vue` 中的全局状态，驱动所有组件的显示/隐藏：

| appState | 含义 | 谁可见 |
|----------|------|--------|
| `idle` | 未开始 | InputForm 可用，PipelineView 空态 |
| `running` | 生成中 | InputForm disabled，PipelineView 当前步蓝色脉冲 |
| `confirming` | 等人确认 | InputForm 三按钮，PipelineView 大纲详情 |
| `done` | 完成 | 全部恢复，ScriptOutput 展示结果 |

**3. autoContinue 触发条件。** 当 `response.step` 不是 `"done"` 且不是 `"wait_confirm"` 时，自动打包 `{confirm_action: "continue", state: currentState}` 发下一次请求。不要在其他状态下触发自动接力。
