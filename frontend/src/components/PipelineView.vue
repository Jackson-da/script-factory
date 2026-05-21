<script setup>
/**
 * 流水线进度组件。
 * 展示策划→写作→审核→修改四个步骤的状态（idle/active/done）。
 * 在确认模式下展示大纲预览。
 */
defineProps({
  steps: { type: Array, default: () => [] },
  outline: { type: Object, default: null },
  appState: { type: String, default: 'idle' },
})
</script>

<template>
  <section class="card pipeline-card">
    <div class="card-header">流水线进度</div>

    <!-- 步骤指示器 -->
    <div class="pipeline-steps">
      <template v-for="(s, i) in steps" :key="s.name">
        <div
          class="pipeline-step"
          :class="{ active: s.status === 'active', done: s.status === 'done', skipped: s.status === 'skipped' }"
        >
          <div class="dot">
            <span v-if="s.status === 'done'">&#10003;</span>
            <span v-else-if="s.status === 'skipped'">—</span>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <div class="label">{{ s.label }}</div>
        </div>
        <div
          v-if="i < steps.length - 1"
          class="connector"
          :class="{
            done: s.status === 'done' && steps[i + 1].status !== 'skipped',
            skipped: steps[i + 1].status === 'skipped'
          }"
        ></div>
      </template>
    </div>

    <!-- Skeleton 占位 -->
    <div v-if="appState === 'running'" class="skeleton-group">
      <div class="skeleton" style="width:60%"></div>
      <div class="skeleton" style="width:80%"></div>
      <div class="skeleton" style="width:40%"></div>
    </div>

    <!-- 大纲预览（确认模式下展示） -->
    <div v-if="outline && appState === 'confirming'" class="outline-preview">
      <div class="outline-title">{{ outline.title }}</div>
      <div class="outline-hook"><strong>钩子：</strong>{{ outline.hook }}</div>
      <div
        v-for="(s, i) in outline.sections"
        :key="i"
        class="outline-section"
      >
        <strong>{{ s.heading }}</strong>
        <span v-if="s.talking_points?.length">
          — {{ s.talking_points.join('；') }}
        </span>
      </div>
      <div v-if="outline.key_phrases?.length" class="outline-phrases">
        <strong>金句：</strong>{{ outline.key_phrases.join(' / ') }}
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!steps.length" class="empty-state">
      填写左侧表单，点击"生成脚本"开始
    </div>
  </section>
</template>

<style scoped>
.pipeline-card { grid-column: span 7; }
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
}
.card-header {
  font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--muted);
  margin-bottom: 20px; padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.pipeline-steps { display: flex; align-items: center; gap: 0; margin-bottom: 24px; }
.pipeline-step { flex: 1; text-align: center; }
.dot {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 8px; font-size: 13px; font-weight: 700;
  border: 2px solid var(--border); background: var(--surface);
  color: var(--muted); transition: all 200ms ease;
}
.pipeline-step.active .dot {
  border-color: var(--primary); background: var(--primary); color: #FFF;
  box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.15);
}
.pipeline-step.done .dot {
  border-color: var(--success); background: var(--success); color: #FFF;
}
.pipeline-step.skipped .dot {
  border: 2px dashed var(--border); background: var(--surface); color: var(--muted);
}
.label { font-size: 12px; color: var(--muted); }
.pipeline-step.active .label { color: var(--primary); font-weight: 700; }
.pipeline-step.done .label { color: var(--success); }
.pipeline-step.skipped .label { color: #94A3B8; }

.connector {
  width: 28px; height: 2px; background: var(--border);
  flex-shrink: 0; margin-bottom: 28px;
}
.connector.done { background: var(--success); }
.connector.skipped { background: none; border-top: 2px dashed var(--border); height: 0; }

/* Skeleton */
.skeleton-group { margin-top: 20px; }
.skeleton {
  height: 14px; margin-bottom: 10px; border-radius: 4px;
  background: linear-gradient(90deg, #E2E8F0 25%, #F1F5F9 50%, #E2E8F0 75%);
  background-size: 800px 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}

/* Outline */
.outline-preview {
  background: #EFF6FF; border: 1px solid #BFDBFE;
  border-radius: var(--radius); padding: 20px;
  font-size: 14px; line-height: 1.9;
}
.outline-title { font-size: 18px; font-weight: 700; margin-bottom: 12px; color: var(--primary); }
.outline-hook { margin-bottom: 8px; }
.outline-section { margin-bottom: 4px; }
.outline-phrases { margin-top: 12px; padding-top: 10px; border-top: 1px solid #BFDBFE; color: var(--accent); }

.empty-state { color: var(--muted); font-size: 14px; text-align: center; padding: 40px 0; }

@media (max-width: 768px) {
  .pipeline-card { grid-column: span 1; }
}
</style>
