<script setup>
/**
 * 流水线进度 + 每步产出展示。
 * 步骤不再是固定 4 个，根据 review_rounds 动态生成。
 * 点击步骤圆点切换查看对应产出。
 */
import { ref, watch } from 'vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
  outline: { type: Object, default: null },
  script: { type: Object, default: null },
  review: { type: Object, default: null },
  reviewRounds: { type: Array, default: () => [] },
  hotspot: { type: Array, default: () => [] },
  appState: { type: String, default: 'idle' },
})

const selectedStep = ref('plan')

// 根据步骤名找到对应的轮次数据
function getRound(name) {
  if (!name || (!name.startsWith('review_') && !name.startsWith('revise_'))) return null
  const n = parseInt(name.split('_')[1])
  return props.reviewRounds?.find(r => r.round === n) || null
}

// 步骤是否有内容可看
function hasContent(name) {
  if (name === 'plan') return !!props.outline
  if (name === 'write') return !!props.script
  if (name.startsWith('review_')) return !!getRound(name)?.review
  if (name.startsWith('revise_')) return !!getRound(name)?.revised_script
  return false
}

// 步骤是否可点击
function isClickable(name) {
  if (!props.steps?.length) return false
  const s = props.steps.find(s => s.name === name)
  if (!s) return false
  return s.status === 'done' || s.status === 'active'
}

function selectStep(name) {
  if (isClickable(name)) selectedStep.value = name
}

// 自动跟随 active 步骤
watch(() => props.steps, (list) => {
  if (!list?.length) return
  const active = list.find(s => s.status === 'active')
  if (active) { selectedStep.value = active.name; return }
  const lastDone = [...list].reverse().find(s => s.status === 'done')
  if (lastDone) selectedStep.value = lastDone.name
}, { deep: true })

// ---- 格式化 ----

const MARKER_STYLES = {
  '[快]':   { bg: '#DBEAFE', fg: '#1D4ED8' },
  '[慢]':   { bg: '#FEF3C7', fg: '#B45309' },
  '[重音]':  { bg: '#FEE2E2', fg: '#DC2626' },
  '[停顿':  { bg: '#E0E7FF', fg: '#4338CA' },
}

function formatScript(content) {
  if (!content) return ''
  let text = content
  text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  text = text.replace(/\[(快|慢|重音|停顿\d+s?)\]/g, (match, inner) => {
    const key = match.startsWith('[停顿') ? '[停顿' : match
    const style = MARKER_STYLES[key] || { bg: '#E2E8F0', fg: '#475569' }
    return `<span class="tone-tag" style="background:${style.bg};color:${style.fg}">${inner}</span>`
  })
  if (text.includes('\n\n')) {
    text = text.split(/\n\n/).map(p => p.replace(/\n/g, '<br>')).join('</p><p>')
  } else if (text.includes('\n')) {
    text = text.replace(/\n/g, '<br>')
  }
  return `<p>${text}</p>`
}

function issueGroupsFrom(reviewData) {
  if (!reviewData?.issues) return []
  const groups = { P0: [], P1: [], P2: [] }
  for (const issue of reviewData.issues) {
    const s = issue.severity || 'P2'
    if (groups[s]) groups[s].push(issue)
  }
  return [
    { label: 'P0 · 合规/法律 · 必须修改', items: groups.P0, cls: 'sg-p0' },
    { label: 'P1 · 事实/数据 · 必须修改', items: groups.P1, cls: 'sg-p1' },
    { label: 'P2 · 风格建议 · 仅记录', items: groups.P2, cls: 'sg-p2' },
  ].filter(g => g.items.length)
}

// 根据字数 + 停顿标记估算真实口播时长
// 中文口播语速约 3.5 字/秒，加上 [停顿Ns] 的秒数
function estimateDuration(content) {
  if (!content) return 0
  // 累计停顿总秒数
  let pauseSec = 0
  const pauses = content.match(/\[停顿(\d+)s?\]/g)
  if (pauses) {
    for (const p of pauses) {
      const n = parseInt(p.match(/\d+/)?.[0])
      if (n) pauseSec += n
    }
  }
  // 剔除所有节奏标记，只算正文
  const text = content.replace(/\[.*?\]/g, '')
  return Math.round(text.length / 3.5 + pauseSec)
}

// 统计纯文本字数（剔除节奏标记）
function charCount(content) {
  if (!content) return 0
  return content.replace(/\[.*?\]/g, '').length
}

// 审核真实状态：passed 且 分数 >= 90 才算通过
function reviewDecision(reviewData) {
  if (!reviewData) return 'pending'
  if (!reviewData.passed) return 'fail'
  return (reviewData.score || 0) >= 90 ? 'pass' : 'fail'
}

const dimNames = { information:'信息量', oral:'口语化', compliance:'合规性', usability:'可用率' }
const dimKeys = ['information', 'oral', 'compliance', 'usability']
const checkNames = { compliance:'合规', facts:'事实', style:'风格' }
</script>

<template>
  <section class="card pipeline-card">
    <div class="card-header">流水线进度</div>

    <!-- 步骤指示器：分两行，上排 dot+连接线，下排 label -->
    <div class="pipeline-steps">
      <div class="step-track">
        <template v-for="(s, i) in steps" :key="s.name">
          <!-- 每列包含 dot + label，保证上下对齐 -->
          <div class="step-col">
            <div
              class="pipeline-step"
              :class="{
                active: s.status === 'active',
                done: s.status === 'done',
                skipped: s.status === 'skipped',
                selected: selectedStep === s.name,
                clickable: isClickable(s.name),
              }"
              @click="selectStep(s.name)"
            >
              <div class="dot">
                <span v-if="s.status === 'done'">&#10003;</span>
                <span v-else-if="s.status === 'skipped'">—</span>
                <span v-else>{{ s.name.startsWith('review_') ? '审' : s.name.startsWith('revise_') ? '改' : i + 1 }}</span>
              </div>
            </div>
            <div
              class="step-label"
              :class="{
                'label-active': s.status === 'active',
                'label-done': s.status === 'done',
                'label-selected': selectedStep === s.name,
              }"
            >
              {{ s.label }}
            </div>
          </div>
          <!-- 步骤间连接线 -->
          <div v-if="i < steps.length - 1" class="step-gap">
            <div
              class="connector"
              :class="{
                done: s.status === 'done' && steps[i + 1].status !== 'skipped',
                skipped: steps[i + 1].status === 'skipped'
              }"
            ></div>
          </div>
        </template>
      </div>
    </div>

    <!-- Skeleton -->
    <div v-if="appState === 'running' && !outline && !script && !review" class="skeleton-group">
      <div class="skeleton" style="width:60%"></div>
      <div class="skeleton" style="width:80%"></div>
      <div class="skeleton" style="width:40%"></div>
    </div>

    <!-- ========== 内容区 ========== -->

    <!-- 策划 -->
    <div v-if="selectedStep === 'plan' && outline" class="step-block">
      <div class="sb-header">
        策划产出 · 大纲
        <span class="sb-badge">{{ outline.sections?.length || 0 }} 段落 · 预估 {{ outline.estimated_duration || '?' }}s</span>
      </div>
      <div class="sb-body outline-body">
        <div class="ol-title">{{ outline.title }}</div>
        <div class="ol-hook"><strong>钩子：</strong>{{ outline.hook }}</div>
        <div v-for="(sec, i) in outline.sections" :key="i" class="ol-sec">
          <strong>{{ i + 1 }}. {{ sec.heading }}</strong>
          <span v-if="sec.talking_points?.length"> — {{ sec.talking_points.join('；') }}</span>
        </div>
        <div v-if="outline.key_phrases?.length" class="ol-kp">
          <strong>金句：</strong>{{ outline.key_phrases.join(' / ') }}
        </div>
        <!-- 热点搜索信息 -->
        <div v-if="hotspot.length" class="hotspot-block">
          <details>
            <summary>搜索热点参考（{{ hotspot.length }} 条结果）</summary>
            <div class="hotspot-list">
              <a
                v-for="(item, i) in hotspot"
                :key="i"
                class="hotspot-card"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
              >
                <div class="hotspot-title">{{ item.title }}</div>
                <div class="hotspot-snippet">{{ item.content?.slice(0, 200) }}</div>
              </a>
            </div>
          </details>
        </div>
        <div v-else class="hotspot-block hotspot-empty">
          未使用搜索热点（无 Tavily API Key 或搜索无结果）
        </div>
      </div>
    </div>

    <!-- 写作 -->
    <div v-if="selectedStep === 'write' && script" class="step-block">
      <div class="sb-header">
        写作产出 · 口播脚本
        <span class="sb-badge">约 {{ estimateDuration(script.content) }}s · {{ charCount(script.content) }} 字</span>
      </div>
      <div class="sb-body script-body" v-html="formatScript(script.content)"></div>
    </div>

    <!-- 审核 N -->
    <div v-if="selectedStep.startsWith('review_') && getRound(selectedStep)?.review" class="step-block">
      <template v-for="(r, ri) in reviewRounds" :key="'rr'+ri">
        <template v-if="selectedStep === 'review_' + r.round">
          <div class="sb-header">
            审核第 {{ r.round }} 轮
            <span class="sb-badge" :class="reviewDecision(r.review) === 'pass' ? 'badge-pass' : 'badge-fail'">
              {{ r.review?.score ?? '?' }} 分 · {{ reviewDecision(r.review) === 'pass' ? '通过' : '需修改' }}
            </span>
          </div>
          <div class="sb-body review-body">
            <!-- 本轮审核所属的脚本：第 1 轮看原始写作结果，后续看上一轮的修改结果 -->
            <details class="review-script-toggle">
              <summary>查看本轮被审核的脚本</summary>
              <div class="script-body" v-html="formatScript(
                r.round === 1
                  ? (script?.content || '')
                  : ((reviewRounds[ri - 1]?.revised_script || script)?.content || '')
              )"></div>
            </details>

            <!-- 评分 -->
            <div class="rv-score-row">
              <div class="rv-score-big">{{ r.review?.score }}</div>
              <div class="rv-score-label">综合评分 / 100</div>
            </div>
            <div class="rv-dim-grid">
              <div v-for="k in dimKeys" :key="k" class="rv-dim-item">
                <div class="rv-dim-name">{{ dimNames[k] }}</div>
                <div class="rv-dim-bar"><div class="rv-dim-fill" :style="{ width: (r.review?.dimension_scores?.[k] || 0) / 25 * 100 + '%' }"></div></div>
                <div class="rv-dim-val">{{ r.review?.dimension_scores?.[k] || 0 }}<span class="rv-dim-max">/25</span></div>
              </div>
            </div>
            <div class="rv-checks">
              <span v-for="(label, key) in checkNames" :key="key" class="rv-check-tag" :class="r.review?.checks?.[key] ? 'check-pass' : 'check-fail'">
                {{ r.review?.checks?.[key] ? '✓' : '✗' }} {{ label }}
              </span>
            </div>

            <!-- Issues -->
            <div v-if="issueGroupsFrom(r.review).length" class="rv-issues">
              <div v-for="group in issueGroupsFrom(r.review)" :key="group.cls" class="rv-ig">
                <div class="rv-ig-h" :class="group.cls">{{ group.label }}（{{ group.items.length }}）</div>
                <div v-for="(issue, j) in group.items" :key="j" class="rv-ig-item" :class="group.cls">
                  <div v-if="issue.location" class="rv-ig-loc">"{{ issue.location }}"</div>
                  <div class="rv-ig-desc">{{ issue.description }}</div>
                  <div v-if="issue.suggestion" class="rv-ig-sug">建议：{{ issue.suggestion }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </template>
    </div>

    <!-- 修改 N -->
    <div v-if="selectedStep.startsWith('revise_') && getRound(selectedStep)?.revised_script" class="step-block">
      <template v-for="(r, ri) in reviewRounds" :key="'rv'+ri">
        <template v-if="selectedStep === 'revise_' + r.round && r.revised_script">
          <div class="sb-header">
            修改第 {{ r.round }} 轮 · 修改后脚本
            <span class="sb-badge">约 {{ estimateDuration(r.revised_script.content) }}s · {{ charCount(r.revised_script.content) }} 字</span>
          </div>
          <div class="sb-body script-body" v-html="formatScript(r.revised_script.content)"></div>
        </template>
      </template>
    </div>

    <!-- 确认模式 -->
    <div v-if="outline && appState === 'confirming'" class="confirm-hint">
      请确认大纲后选择操作：继续 / 重新策划 / 修改要求
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
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px;
}
.card-header {
  font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--muted);
  margin-bottom: 20px; padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

/* ---- 步骤指示器：单行 flex，每列 dot+label 垂直堆叠 ---- */
.pipeline-steps { margin-bottom: 20px; overflow-x: auto; }

.step-track {
  display: inline-flex;
  align-items: flex-start;
  min-width: 100%;
}

.step-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 48px;
  flex-shrink: 0;
  padding-top: 6px;
}

.pipeline-step { text-align: center; }
.pipeline-step.clickable { cursor: pointer; }
.pipeline-step.clickable:hover .dot { transform: scale(1.1); }

.dot {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto; font-size: 13px; font-weight: 700;
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
.pipeline-step.selected .dot { box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2); }

/* 连接线列：高度对齐 dot，连接线垂直居中 */
.step-gap {
  width: 24px;
  flex-shrink: 0;
  height: 36px;
  margin-top: 6px;
  display: flex;
  align-items: center;
}

.connector {
  width: 100%;
  height: 2px;
  background: var(--border);
  transition: background 200ms ease;
}
.connector.done { background: var(--success); }

/* 标签：紧跟 dot 下方 */
.step-label {
  font-size: 11px;
  line-height: 1.3;
  color: var(--muted);
  margin-top: 6px;
  text-align: center;
  word-break: keep-all;
  transition: color 200ms ease;
}
.step-label.label-active { color: var(--primary); font-weight: 700; }
.step-label.label-done { color: var(--success); }
.step-label.label-selected { color: var(--primary); font-weight: 700; }

/* ---- Skeleton ---- */
.skeleton-group { margin-top: 20px; }
.skeleton {
  height: 14px; margin-bottom: 10px; border-radius: 4px;
  background: linear-gradient(90deg, #E2E8F0 25%, #F1F5F9 50%, #E2E8F0 75%);
  background-size: 800px 100%; animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}

/* ---- 产出块 ---- */
.step-block {
  border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden;
}
.sb-header {
  font-size: 13px; font-weight: 700; color: var(--fg);
  padding: 12px 16px; background: #F8FAFC;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
}
.sb-badge {
  margin-left: auto; font-size: 11px; font-weight: 400;
  color: var(--muted); background: var(--surface);
  padding: 2px 8px; border-radius: 12px; border: 1px solid var(--border);
}
.badge-pass { color: var(--success); border-color: var(--success); }
.badge-fail { color: var(--danger); border-color: var(--danger); }
.sb-body { padding: 16px; font-size: 14px; line-height: 1.8; max-height: 400px; overflow-y: auto; }

/* ---- 大纲 ---- */
.outline-body { background: #EFF6FF; }
.ol-title { font-size: 18px; font-weight: 700; color: var(--primary); margin-bottom: 8px; }
.ol-hook { margin-bottom: 8px; }
.ol-sec { margin-bottom: 4px; }
.ol-kp { margin-top: 12px; padding-top: 10px; border-top: 1px solid #BFDBFE; color: var(--accent); }

/* ---- 热点搜索 ---- */
.hotspot-block { margin-top: 14px; padding-top: 12px; border-top: 1px solid #BFDBFE; }
.hotspot-block summary {
  font-size: 12px; font-weight: 600; color: var(--muted);
  cursor: pointer; user-select: none;
}
.hotspot-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.hotspot-card {
  display: block; padding: 10px 14px; border-radius: 6px;
  border: 1px solid var(--border); background: #FFF;
  text-decoration: none; transition: border-color 150ms ease;
}
.hotspot-card:hover { border-color: var(--primary); }
.hotspot-title {
  font-size: 13px; font-weight: 600; color: var(--primary);
  margin-bottom: 4px; line-height: 1.4;
}
.hotspot-snippet {
  font-size: 12px; color: var(--muted); line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
.hotspot-empty {
  font-size: 12px; color: var(--muted); font-style: italic;
}

/* ---- 脚本 ---- */
.script-body { background: #F8FAFC; font-size: 15px; color: #1E293B; }
.script-body :deep(p) { margin: 0 0 12px 0; }
.script-body :deep(p:last-child) { margin-bottom: 0; }
.script-body :deep(.tone-tag) {
  display: inline-block; font-size: 11px; font-weight: 700;
  padding: 1px 6px; border-radius: 4px; margin: 0 2px;
  vertical-align: middle; line-height: 1.6;
}

/* ---- 审核 ---- */
.review-body { background: #FFF; }
.review-script-toggle { margin-bottom: 14px; font-size: 13px; }
.review-script-toggle summary {
  cursor: pointer; color: var(--primary); font-weight: 600;
  padding: 4px 0;
}
.review-script-toggle .script-body { margin-top: 8px; max-height: 240px; overflow-y: auto; }

.rv-score-row { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.rv-score-big { font-size: 36px; font-weight: 700; color: var(--primary); }
.rv-score-label { font-size: 13px; color: var(--muted); }
.rv-dim-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; margin-bottom: 14px; }
.rv-dim-item { display: grid; grid-template-columns: 48px 1fr 36px; align-items: center; gap: 8px; }
.rv-dim-name { font-size: 12px; color: var(--muted); text-align: right; }
.rv-dim-bar { height: 6px; background: #E2E8F0; border-radius: 3px; overflow: hidden; }
.rv-dim-fill { height: 100%; background: var(--primary); border-radius: 3px; }
.rv-dim-val { font-size: 13px; font-weight: 700; }
.rv-dim-max { font-weight: 400; color: var(--muted); font-size: 11px; }

.rv-checks { display: flex; gap: 8px; margin-bottom: 10px; }
.rv-check-tag { font-size: 11px; padding: 2px 10px; border-radius: 12px; font-weight: 600; }
.check-pass { background: #ECFDF5; color: var(--success); }
.check-fail { background: #FEF2F2; color: var(--danger); }

/* ---- Issues ---- */
.rv-issues { margin-top: 10px; }
.rv-ig { margin-bottom: 8px; }
.rv-ig-h { font-size: 12px; font-weight: 700; margin-bottom: 4px; }
.rv-ig-h.sg-p0 { color: var(--danger); }
.rv-ig-h.sg-p1 { color: var(--warning); }
.rv-ig-h.sg-p2 { color: var(--secondary); }
.rv-ig-item {
  font-size: 13px; line-height: 1.6; padding: 8px 12px;
  border-radius: 6px; margin-bottom: 5px;
}
.rv-ig-item.sg-p0 { background: #FEF2F2; border-left: 3px solid var(--danger); }
.rv-ig-item.sg-p1 { background: #FFF7ED; border-left: 3px solid var(--warning); }
.rv-ig-item.sg-p2 { background: #F0F9FF; border-left: 3px solid var(--secondary); }
.rv-ig-loc { font-style: italic; color: var(--muted); margin-bottom: 2px; }
.rv-ig-desc { color: var(--fg); }
.rv-ig-sug { color: var(--muted); font-size: 12px; margin-top: 2px; }

/* ---- 其他 ---- */
.confirm-hint {
  background: #EFF6FF; border: 1px solid #BFDBFE;
  border-radius: var(--radius); padding: 12px 16px;
  font-size: 13px; color: var(--primary); text-align: center;
}
.empty-state { color: var(--muted); font-size: 14px; text-align: center; padding: 40px 0; }

@media (max-width: 768px) {
  .pipeline-card { grid-column: span 1; }
  .rv-dim-grid { grid-template-columns: 1fr; }
}
</style>
