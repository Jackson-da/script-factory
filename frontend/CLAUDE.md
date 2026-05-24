# CLAUDE.md — frontend

前端专属指南。跨模块内容见根目录 `CLAUDE.md`。

子目录指南：`src/components/CLAUDE.md` — 组件分工、节奏标记颜色映射、appState 流转规则

## 命令

```bash
npm --prefix frontend install          # 安装依赖
npm --prefix frontend run dev          # 开发服务器（端口 5173）
npm --prefix frontend run build        # 生产构建
```

Vite 开发服务器通过 proxy 把 `/generate` 和 `/health` 转发到 `http://localhost:8000`。

## 组件树

```
App.vue (全局状态: appState ∈ {idle, running, confirming, done})
├── InputForm.vue    (左侧5列) — 表单输入 + 确认按钮组 + 反馈面板
├── PipelineView.vue (右侧7列) — 进度条 + skeleton 占位 + 大纲预览
└── ScriptOutput.vue (底部全宽) — 脚本全文(节奏标记高亮) + 元信息栏 + issue 列表
```

## appState 驱动 UI

| appState | InputForm | PipelineView | ScriptOutput |
|----------|-----------|-------------|--------------|
| `idle` | 可用 | "填写表单开始"灰提示 | 隐藏 |
| `running` | disabled + "生成中..." | 当前步蓝色脉冲 + skeleton | 隐藏 |
| `confirming` | 三按钮(确认大纲/重新策划/修改) | 大纲详情 | 隐藏 |
| `done` | 恢复可用 | 全部绿色 done | 完整结果 |

## 全自动接力 (`App.vue`)

```javascript
function updateResponse(data) {
  Object.assign(response, data)
  currentState = data.state
  if (data.step === 'done') {
    appState.value = 'done'
  } else if (data.step === 'wait_confirm') {
    appState.value = 'confirming'
  } else {
    appState.value = 'running'
    autoContinue()  // 自动发 confirm 请求推进下一步
  }
}
```

`autoContinue()` 打包 `{confirm_action: 'continue', state: currentState}` 调 `confirmAction()` → POST /generate。

## API 封装 (`src/api/index.js`)

两个函数：
- `generateScript({topic, style, duration, auto_mode})` → POST /generate
- `confirmAction({confirm_action, feedback, state})` → POST /generate

两者调同一个端点，靠 body 字段区分。均返回 `GenerateResponse`。

## 设计系统

Swiss Modernism 2.0：
- 主色 `#2563EB`，点缀 `#F97316`（确认按钮/金句）
- 成功 `#059669`，危险 `#DC2626`
- 字体 Atkinson Hyperlegible
- 12 列 CSS Grid，768px 以下单列堆叠

## 节奏标记渲染 (`ScriptOutput.vue`)

口播稿中的标记被正则替换为带颜色标签：

| 标记 | 底色 | 字色 |
|------|------|------|
| `[快]` | `#DBEAFE` | `#1D4ED8` |
| `[慢]` | `#FEF3C7` | `#B45309` |
| `[重音]` | `#FEE2E2` | `#DC2626` |
| `[停顿Ns]` | `#E0E7FF` | `#4338CA` |
