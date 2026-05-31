<script setup>
/**
 * 脚本输出组件。
 * 展示口播脚本全文 + 审核评分 + 修改轮次 + 未解决问题。
 * 节奏标记([快]/[慢]/[重音]/[停顿])高亮为彩色标签。
 */
import { computed } from 'vue'

const props = defineProps({
  script: { type: Object, default: null },
  review: { type: Object, default: null },
  revisionCount: { type: Number, default: 0 },
  grade: { type: String, default: 'normal' },
  elapsedTime: { type: Number, default: 0 },
  unresolvedIssues: { type: Array, default: () => [] },
  appState: { type: String, default: 'idle' },
})

// 把节奏标记渲染成带颜色的 HTML
const MARKER_STYLES = {
  '[快]':   { bg: '#DBEAFE', fg: '#1D4ED8', label: '快' },
  '[慢]':   { bg: '#FEF3C7', fg: '#B45309', label: '慢' },
  '[重音]':  { bg: '#FEE2E2', fg: '#DC2626', label: '重音' },
  '[停顿':  { bg: '#E0E7FF', fg: '#4338CA', label: null },  // [停顿1s]/[停顿2s] 合并匹配
}

const formattedContent = computed(() => {
  if (!props.script?.content) return ''
  let text = props.script.content

  // 转义 HTML 特殊字符
  text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 匹配所有节奏标记: [快] [慢] [重音] [停顿Ns]
  text = text.replace(/\[(快|慢|重音|停顿\d+s?)\]/g, (match, inner) => {
    const key = match.startsWith('[停顿') ? '[停顿' : match
    const style = MARKER_STYLES[key] || { bg: '#E2E8F0', fg: '#475569' }
    const label = style.label || inner
    return `<span class="tone-marker" style="background:${style.bg};color:${style.fg}">${label}</span>`
  })

  // 段落处理：先按双换行分大段（语义段落），内部单换行转为 <br>
  if (text.includes('\n\n')) {
    // 有双换行 → 按双换行分段落，段内单换行变分行
    text = text.split(/\n\n/).map(para =>
      para.replace(/\n/g, '<br>')
    ).join('</p><p class="script-p">')
  } else if (text.includes('\n')) {
    // 只有单换行 → 按单换行分行
    text = text.replace(/\n/g, '<br>')
  }
  // 如果完全没有换行，尝试在中文句号后加 <br> 分行
  // （不拆分段落，只加视觉换行）
  if (!text.includes('\n\n') && !text.includes('<br>')) {
    text = text.replace(/([。！？])(?=[^\s])/g, '$1<br>')
  }
  text = `<p class="script-p">${text}</p>`

  return text
})
</script>

<template>
  <section class="card output-card">
    <div class="card-header">生成结果</div>

    <!-- 空状态 -->
    <div v-if="!script" class="empty-state">
      填写左侧表单，点击"生成脚本"开始
    </div>

    <!-- 有脚本内容 -->
    <template v-else>
      <!-- 脚本全文 —— 带节奏标记高亮 -->
      <div class="script-body" v-html="formattedContent"></div>

      <!-- 元信息栏 -->
      <div class="meta-bar">
        <div class="meta-item">
          <div class="meta-label">审核评分</div>
          <div class="meta-value" :class="review?.score >= 90 ? 'score-high' : 'score-low'">
            {{ review?.score ?? '—' }}
          </div>
        </div>
        <div class="meta-item">
          <div class="meta-label">修改轮次</div>
          <div class="meta-value">{{ revisionCount }}</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">状态</div>
          <div class="meta-value" :class="grade === 'degraded' ? 'grade-degraded' : ''">
            {{ grade === 'degraded' ? '降级' : '通过' }}
          </div>
        </div>
        <div class="meta-item">
          <div class="meta-label">耗时</div>
          <div class="meta-value">{{ elapsedTime.toFixed(1) }}s</div>
        </div>
      </div>

      <!-- 图例 -->
      <div class="marker-legend">
        <span class="legend-item"><span class="tone-dot" style="background:#DBEAFE;color:#1D4ED8">快</span> 快节奏</span>
        <span class="legend-item"><span class="tone-dot" style="background:#FEF3C7;color:#B45309">慢</span> 慢节奏</span>
        <span class="legend-item"><span class="tone-dot" style="background:#FEE2E2;color:#DC2626">重音</span> 强调</span>
        <span class="legend-item"><span class="tone-dot" style="background:#E0E7FF;color:#4338CA">停顿</span> 停顿</span>
      </div>

      <!-- 未解决问题列表 -->
      <div v-if="unresolvedIssues.length" class="issues-section">
        <div class="issues-header">未解决问题（需人工处理）</div>
        <div
          v-for="(issue, i) in unresolvedIssues"
          :key="i"
          class="issue-item"
          :class="issue.severity"
        >
          <span class="issue-severity">{{ issue.severity }}</span>
          <div>
            <div v-if="issue.location" class="issue-location">"{{ issue.location }}"</div>
            <div class="issue-desc">{{ issue.description }}</div>
            <div v-if="issue.suggestion" class="issue-suggestion">
              建议：{{ issue.suggestion }}
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.output-card { grid-column: span 12; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px;
}
.card-header {
  font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--muted);
  margin-bottom: 20px; padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

/* 脚本正文 —— 提词器风格 */
.script-body {
  background: #F8FAFC; border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px 32px;
  font-size: 17px; line-height: 2.2; color: #1E293B;
  max-height: 480px; overflow-y: auto;
}
.script-body :deep(.script-p) {
  margin: 0 0 16px 0;
}
.script-body :deep(.script-p:last-child) { margin-bottom: 0; }

/* 节奏标记标签 */
.script-body :deep(.tone-marker) {
  display: inline-block; font-size: 11px; font-weight: 700;
  padding: 1px 6px; border-radius: 4px; margin: 0 2px;
  vertical-align: middle; line-height: 1.6;
  letter-spacing: 0.03em;
}

/* 图例 */
.marker-legend {
  display: flex; gap: 16px; flex-wrap: wrap;
  margin-top: 12px; font-size: 12px; color: var(--muted);
}
.legend-item { display: flex; align-items: center; gap: 4px; }
.tone-dot {
  display: inline-block; font-size: 10px; font-weight: 700;
  padding: 1px 5px; border-radius: 3px; line-height: 1.4;
}

.meta-bar {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 16px; margin-top: 20px; padding-top: 20px;
  border-top: 1px solid var(--border);
}
.meta-label {
  font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--muted);
}
.meta-value { font-size: 20px; font-weight: 700; }
.score-high { color: var(--success); }
.score-low { color: var(--danger); }
.grade-degraded { color: var(--warning); }

.issues-section { margin-top: 20px; }
.issues-header {
  font-size: 13px; font-weight: 700; color: var(--danger); margin-bottom: 12px;
}
.issue-item {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 10px 14px; border-radius: var(--radius);
  margin-bottom: 8px; font-size: 13px; line-height: 1.5;
}
.issue-item.P0 { background: #FEF2F2; border-left: 3px solid var(--danger); }
.issue-item.P1 { background: #FFF7ED; border-left: 3px solid var(--warning); }
.issue-item.P2 { background: #F0F9FF; border-left: 3px solid var(--secondary); }
.issue-severity { font-weight: 700; font-size: 11px; text-transform: uppercase; flex-shrink: 0; }
.issue-item.P0 .issue-severity { color: var(--danger); }
.issue-item.P1 .issue-severity { color: var(--warning); }
.issue-item.P2 .issue-severity { color: var(--secondary); }
.issue-desc { color: var(--fg); }
.issue-suggestion { color: var(--muted); font-size: 12px; margin-top: 2px; }

.empty-state { color: var(--muted); font-size: 14px; text-align: center; padding: 40px 0; }

@media (max-width: 768px) {
  .output-card { grid-column: span 1; }
  .meta-bar { grid-template-columns: repeat(2, 1fr); }
  .script-body { font-size: 15px; padding: 20px; }
}
</style>
