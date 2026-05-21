<script setup>
/**
 * 根组件 —— 管理全局状态和三个子组件的通信。
 *
 * 状态流转：
 * idle → running → (confirming) → done
 *
 * 所有数据通过 props 向下传递，子组件通过 emit 向上通知。
 */
import { ref, reactive, nextTick } from 'vue'
import { generateScript, confirmAction } from './api/index.js'
import InputForm from './components/InputForm.vue'
import PipelineView from './components/PipelineView.vue'
import ScriptOutput from './components/ScriptOutput.vue'

// 页面状态
const appState = ref('idle')  // idle | running | confirming | done
const response = reactive({
  step: 'plan',
  steps: [],
  outline: null,
  script: null,
  review: null,
  revision_count: 0,
  grade: 'normal',
  needs_human: false,
  unresolved_issues: [],
  elapsed_time: 0,
})
// 保存完整 state 用于确认/继续调用
let currentState = null

// 初始步骤模板（点击生成时立即展示，不要等 API 返回）
const INIT_STEPS = [
  { name: 'plan', status: 'idle', label: '策划' },
  { name: 'write', status: 'idle', label: '写作' },
  { name: 'review', status: 'idle', label: '审核' },
  { name: 'revise', status: 'idle', label: '修改' },
]

// 发起生成
async function handleGenerate(params) {
  appState.value = 'running'
  // 立即展示步骤条，策划置为 active
  response.steps = INIT_STEPS.map(s => ({ ...s, status: s.name === 'plan' ? 'active' : 'idle' }))
  try {
    const data = await generateScript(params)
    await updateResponse(data)  // ← await 确保递归链的错误也能被 try/catch 捕获
  } catch (e) {
    alert('生成失败: ' + e.message)
    appState.value = 'idle'
    response.steps = []
  }
}

// 确认操作（确认继续/重新策划/修改要求）
async function handleConfirm(action) {
  appState.value = 'running'
  try {
    const data = await confirmAction({
      confirm_action: action.action,
      feedback: action.feedback || '',
      state: currentState,
    })
    await updateResponse(data)  // ← await 确保后续步骤递归链被正确等待
  } catch (e) {
    alert('操作失败: ' + e.message)
    appState.value = 'idle'
  }
}

// 自动接力：把当前 state 作为 confirm 请求发回后端，推进到下一步
// 不人为加延迟。nextTick 确保 Vue 把当前步状态刷到 DOM，
// 之后 confirmAction 调 LLM 的自然耗时（5-10s）就是浏览器绘制窗口。
async function autoContinue() {
  await nextTick()  // Vue 响应式 → DOM
  try {
    const data = await confirmAction({
      confirm_action: 'continue',
      feedback: '',
      state: currentState,
    })
    await updateResponse(data)
  } catch (e) {
    alert('生成失败: ' + e.message)
    appState.value = 'idle'
  }
}

// 重置所有状态
function handleReset() {
  appState.value = 'idle'
  Object.assign(response, {
    step: 'plan', steps: [], outline: null, script: null, review: null,
    revision_count: 0, grade: 'normal', needs_human: false,
    unresolved_issues: [], elapsed_time: 0,
  })
  currentState = null
}

// 更新本地响应数据，自动模式下自动接力下一步
// 注意：必须 async/await，等 autoContinue 完成后再返回，确保步骤逐个执行而非并发堆叠
async function updateResponse(data) {
  Object.assign(response, data)
  currentState = data.state || data

  if (data.step === 'done') {
    appState.value = 'done'
  } else if (data.step === 'wait_confirm') {
    appState.value = 'confirming'
  } else {
    // 中间步骤(plan→write→review→revise)：保持 running 状态，自动调用下一步
    appState.value = 'running'
    await autoContinue()  // ← 必须 await：等这一步完成并渲染后才推进下一步
  }
}
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <h1>口播脚本生成工厂</h1>
      <p class="app-subtitle">MCN 多Agent协作 — 策划 · 写作 · 审核 · 修改</p>
    </header>

    <div class="app-grid">
      <InputForm
        :disabled="appState === 'running'"
        @generate="handleGenerate"
        @confirm="handleConfirm"
        @reset="handleReset"
        :app-state="appState"
        :outline="response.outline"
      />

      <PipelineView
        :steps="response.steps"
        :outline="response.outline"
        :app-state="appState"
      />

      <ScriptOutput
        :script="response.script"
        :review="response.review"
        :revision-count="response.revision_count"
        :grade="response.grade"
        :elapsed-time="response.elapsed_time"
        :unresolved-issues="response.unresolved_issues"
        :app-state="appState"
      />
    </div>
  </div>
</template>

<style>
/* Swiss Modernism 2.0 设计系统 */
:root {
  --primary: #2563EB;
  --primary-hover: #1D4ED8;
  --secondary: #3B82F6;
  --accent: #F97316;
  --bg: #F8FAFC;
  --surface: #FFFFFF;
  --fg: #1E293B;
  --muted: #64748B;
  --border: #E2E8F0;
  --success: #059669;
  --danger: #DC2626;
  --warning: #D97706;
  --radius: 8px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Atkinson Hyperlegible', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
}

.app-container {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 24px 80px;
}

.app-header {
  margin-bottom: 40px;
}
.app-header h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.app-subtitle {
  font-size: 15px;
  color: var(--muted);
  margin-top: 4px;
}

.app-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 24px;
  align-items: start;
}

/* 响应式：768px以下堆叠 */
@media (max-width: 768px) {
  .app-container { padding: 20px 16px 60px; }
  .app-grid { grid-template-columns: 1fr; }
}
</style>
