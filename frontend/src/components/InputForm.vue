<script setup>
/**
 * 输入表单组件。
 * 收集选题、风格、时长、全自动开关。
 * 运行中显示确认按钮组（确认/重新策划/修改要求）。
 */
import { ref } from 'vue'

const props = defineProps({
  disabled: Boolean,
  appState: String,      // idle | running | confirming | done
  outline: Object | null,
})

const emit = defineEmits(['generate', 'confirm', 'reset'])

const topic = ref('')
const style = ref('知识')
const duration = ref(120)
const autoMode = ref(true)

// 确认相关
const showFeedback = ref(false)
const feedbackMode = ref('')  // 'replan' | 'revise'
const feedback = ref('')

function onSubmit() {
  if (!topic.value.trim()) return
  emit('generate', {
    topic: topic.value.trim(),
    style: style.value,
    duration: duration.value,
    auto_mode: autoMode.value,
  })
}

function onConfirm(type) {
  if (type === 'continue') {
    emit('confirm', { action: 'continue', feedback: '' })
  } else {
    // replan 或 revise_outline
    if (!showFeedback.value || feedbackMode.value !== type) {
      showFeedback.value = true
      feedbackMode.value = type
      feedback.value = ''
      return
    }
    const action = type === 'replan' ? 'replan' : 'revise_outline'
    emit('confirm', { action, feedback: feedback.value })
    showFeedback.value = false
  }
}

function onReset() {
  topic.value = ''
  style.value = '知识'
  duration.value = 120
  autoMode.value = true
  showFeedback.value = false
  emit('reset')
}
</script>

<template>
  <section class="card input-card">
    <div class="card-header">生成配置</div>

    <form @submit.prevent="onSubmit">
      <!-- 选题 -->
      <div class="form-group">
        <label for="topic">选题主题</label>
        <span class="hint">一句话描述要写的话题</span>
        <input
          id="topic"
          v-model="topic"
          type="text"
          placeholder="例：打工人如何保持精力旺盛"
          :disabled="disabled"
        >
      </div>

      <!-- 风格 -->
      <div class="form-group">
        <label for="style">账号风格</label>
        <select id="style" v-model="style" :disabled="disabled">
          <option value="知识">知识科普</option>
          <option value="搞笑">搞笑吐槽</option>
          <option value="情感">情感共鸣</option>
        </select>
      </div>

      <!-- 时长 -->
      <div class="form-group">
        <label for="duration">目标时长</label>
        <select id="duration" v-model.number="duration" :disabled="disabled">
          <option :value="60">60秒 (约 120 字)</option>
          <option :value="120">120秒 (约 240 字)</option>
          <option :value="180">180秒 (约 360 字)</option>
        </select>
      </div>

      <!-- 全自动开关 -->
      <div class="form-group auto-toggle">
        <label>
          <input type="checkbox" v-model="autoMode" :disabled="disabled">
          全自动模式（策划完成后自动继续）
        </label>
      </div>

      <!-- idle/done 状态：生成按钮 -->
      <button
        v-if="appState === 'idle' || appState === 'done'"
        type="submit"
        class="btn btn-primary"
        :disabled="disabled || !topic.trim()"
      >
        {{ appState === 'done' ? '重新生成' : '生成脚本' }}
      </button>

      <!-- running 状态：禁用 -->
      <button
        v-else-if="appState === 'running'"
        class="btn btn-primary"
        disabled
      >
        生成中...
      </button>

      <!-- confirming 状态：确认按钮组 -->
      <div v-else-if="appState === 'confirming'" class="confirm-group">
        <button type="button" class="btn btn-accent" @click="onConfirm('continue')">
          确认大纲，继续
        </button>
        <button type="button" class="btn btn-outline" @click="onConfirm('replan')">
          重新策划
        </button>
        <button type="button" class="btn btn-outline" @click="onConfirm('revise')">
          修改要求
        </button>

        <!-- 反馈输入区 -->
        <div v-if="showFeedback" class="feedback-panel">
          <label>
            {{ feedbackMode === 'replan' ? '重新策划说明（可选）' : '修改要求' }}
          </label>
          <textarea
            v-model="feedback"
            :placeholder="feedbackMode === 'replan'
              ? '例：换个角度切入，不要太说教...'
              : '例：第二部分加两个真实案例...'"
            rows="3"
          ></textarea>
          <button type="button" class="btn btn-accent btn-sm" @click="onConfirm(feedbackMode)">
            确认{{ feedbackMode === 'replan' ? '重新策划' : '修改' }}
          </button>
        </div>
      </div>

      <!-- 恢复初始按钮 -->
      <button
        v-if="appState === 'done'"
        type="button"
        class="btn btn-outline"
        style="margin-top:8px"
        @click="onReset"
      >
        清空重新开始
      </button>
    </form>
  </section>
</template>

<style scoped>
.input-card {
  grid-column: span 5;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
}
.card-header {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.form-group {
  margin-bottom: 20px;
}
.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: var(--fg);
  margin-bottom: 6px;
}
.hint {
  font-size: 12px;
  color: var(--muted);
}
.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 14px;
  font-size: 15px;
  font-family: inherit;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--fg);
  transition: border-color 150ms ease;
  outline: none;
}
.form-group input:focus,
.form-group select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.auto-toggle {
  font-size: 13px;
}
.auto-toggle input {
  width: auto;
  margin-right: 6px;
  accent-color: var(--primary);
}
.btn {
  width: 100%;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 700;
  font-family: inherit;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 150ms ease;
  margin-bottom: 8px;
}
.btn-primary { background: var(--primary); color: #FFF; }
.btn-primary:hover:not(:disabled) { background: var(--primary-hover); }
.btn-accent { background: var(--accent); color: #FFF; }
.btn-accent:hover { background: #EA580C; }
.btn-outline {
  background: var(--surface);
  color: var(--muted);
  border: 1px solid var(--border);
}
.btn-outline:hover { background: #F1F5F9; color: var(--fg); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm { width: auto; padding: 8px 16px; font-size: 14px; }

.confirm-group { margin-top: 4px; }
.feedback-panel {
  background: #FFF7ED;
  border: 1px solid #FED7AA;
  border-radius: var(--radius);
  padding: 16px;
  margin-top: 12px;
}
.feedback-panel textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 13px;
  resize: vertical;
  min-height: 60px;
}

@media (max-width: 768px) {
  .input-card { grid-column: span 1; }
}
</style>
