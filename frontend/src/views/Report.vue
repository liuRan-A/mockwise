<template>
  <div class="container">
    <StepsIndicator :current="4" />

    <a-spin :spinning="loading">
      <template v-if="report">
        <!-- Hero -->
        <div class="report-hero">
          <div class="score-card mw-card">
            <ScoreRing :score="report.total_score" />
            <span class="score-label">综合得分 · 超过同岗位 {{ report.comparison?.percentile || 0 }}% 的考生</span>
            <span class="mw-chip" :class="lastDeltaClass">
              本次较上场 {{ lastDeltaText }}
            </span>
          </div>

          <div class="summary-card mw-card">
            <h3>本场概览</h3>
            <p style="color:var(--text-2); font-size:13px; margin:0;">{{ report.overview }}</p>
            <div class="summary-grid">
              <div class="summary-stat"><div class="v">{{ doneCount }} / {{ (report.questions || []).length }}</div><div class="l">完成题目</div></div>
              <div class="summary-stat"><div class="v">{{ Math.round(report.duration_sec / 60) }} min</div><div class="l">总用时</div></div>
              <div class="summary-stat">
                <div class="v" :style="{ color: (report.comparison?.last_delta || 0) >= 0 ? 'var(--success)' : 'var(--warning)' }">
                  {{ lastDeltaText }}
                </div>
                <div class="l">较上场</div>
              </div>
            </div>
          </div>
        </div>

        <div class="two-col">
          <!-- 分维度 -->
          <div class="mw-card">
            <h3>分维度得分</h3>
            <div class="dim-list">
              <DimensionBar
                v-for="d in (report.dimensions || [])"
                :key="d.name"
                :name="d.name" :score="d.score"
              />
            </div>
            <div class="report-actions">
              <a-button size="large" block @click="$router.push(`/question/${report.session_id}/${(report.questions || [])[0]?.session_question_id}`)">
                查看逐题回放
              </a-button>
              <a-button size="large" block class="mw-btn-dark" :loading="practicingAll" @click="practiceWeak">针对薄弱项加练 →</a-button>
            </div>
          </div>

          <!-- 逐题回顾：含每题分析（答得好/欠缺）+ 参考答案 -->
          <div class="mw-card">
            <h3>逐题回顾与逐题分析</h3>
            <div class="q-list">
              <div
                v-for="q in (report.questions || [])"
                :key="q.session_question_id"
                class="q-item-wrap"
              >
                <div class="q-item" @click="toggleQ(q.session_question_id)">
                  <div class="label">
                    第 {{ q.seq }} 题 · {{ q.category }}
                    <small>耗时 {{ fmtMs(q.duration_ms) }}<template v-if="q.followup_count"> · 追问 {{ q.followup_count }} 次</template>
                      <template v-if="q.total_score != null && q.total_score < 70"> · <b style="color:var(--warning)">薄弱题</b></template>
                    </small>
                  </div>
                  <div class="score" :style="{ color: scoreColor(q.total_score) }">
                    {{ q.total_score ? Math.round(q.total_score) : '-' }}
                  </div>
                  <div class="arrow">{{ expandedQ === q.session_question_id ? '收起 ▲' : '分析 ▼' }}</div>
                </div>

                <!-- 展开区：答得好 / 欠缺 / 参考答案 / 再练一轮 -->
                <div v-if="expandedQ === q.session_question_id" class="q-analysis">
                  <div class="q-title-line">{{ q.content }}</div>

                  <div class="ana-block good" v-if="(q.good_points || []).length">
                    <div class="ana-title">✅ 答得好的地方</div>
                    <ul><li v-for="(g, i) in q.good_points" :key="'g' + i">{{ g }}</li></ul>
                  </div>
                  <div class="ana-block bad" v-if="(q.weak_points || []).length">
                    <div class="ana-title">📝 欠缺 / 待改进</div>
                    <ul><li v-for="(w, i) in q.weak_points" :key="'w' + i">{{ w }}</li></ul>
                  </div>
                  <div class="ana-block" v-if="q.ref_answer">
                    <div class="ana-title" style="cursor:pointer;" @click="showRef = !showRef">
                      📖 参考标准答案 <span style="font-size:11px;color:var(--text-3);">{{ showRef ? '（点击收起）' : '（点击展开）' }}</span>
                    </div>
                    <p v-if="showRef" class="ref-text">{{ q.ref_answer }}</p>
                  </div>

                  <div class="ana-ops">
                    <a-button size="small" @click="$router.push(`/question/${report.session_id}/${q.session_question_id}`)">查看逐题回放 ›</a-button>
                    <a-button size="small" type="primary" ghost
                      v-if="q.total_score != null && q.total_score < 75"
                      :loading="practicing === q.session_question_id"
                      @click="practiceCategory(q)">针对该题型再练一轮 →</a-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 高光时刻 + 改进建议 -->
        <!-- 本场薄弱题速览（按题分数 < 70 自动识别） -->
        <div class="mw-card" style="margin-top:16px;" v-if="weakQuestionsInReport.length">
          <h3>本场答得不好的题（{{ weakQuestionsInReport.length }}）</h3>
          <div class="weak-grid">
            <div v-for="q in weakQuestionsInReport" :key="q.session_question_id" class="weak-row">
              <div class="weak-meta">
                <div class="weak-cat">{{ q.category }}</div>
                <div class="weak-title">{{ q.content }}</div>
              </div>
              <div class="weak-score" :style="{ color: 'var(--warning)' }">
                {{ Math.round(q.total_score) }}
              </div>
              <a-button size="small" type="primary" ghost :loading="practicing === q.session_question_id"
                @click="practiceCategory(q)">针对该题型再练 →</a-button>
            </div>
          </div>
        </div>

        <div class="two-col" style="margin-top:16px;">
          <div class="mw-card">
            <h3>高光时刻</h3>
            <div class="highlight-list">
              <div v-for="(h, i) in report.highlights" :key="i" class="highlight-row">
                <span class="ts">{{ fmtTs(h.ts_ms) }}</span>
                <span class="snippet">{{ h.snippet }}</span>
              </div>
              <a-empty v-if="!report.highlights.length" description="暂无高光片段" />
            </div>
          </div>
          <div class="mw-card">
            <h3>改进建议与推荐加练</h3>
            <div class="rec-list">
              <div v-for="(r, i) in (report.recommendations || [])" :key="i" class="rec-item">
                <span class="mw-tag" :class="recTagClass(r.kind)">{{ recLabel(r.kind) }}</span>
                <span class="content">{{ r.content }}</span>
              </div>
              <a-empty v-if="!(report.recommendations || []).length" description="暂无建议" />
            </div>
          </div>
        </div>

        <div style="margin-top:24px; text-align:center;">
          <a-space size="large">
            <a-button size="large" @click="$router.push('/dashboard')">返回工作台</a-button>
            <a-button type="primary" size="large" @click="$router.push('/form')">再练一场</a-button>
          </a-space>
        </div>
      </template>
    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import StepsIndicator from '@/components/StepsIndicator.vue'
import ScoreRing from '@/components/ScoreRing.vue'
import DimensionBar from '@/components/DimensionBar.vue'
import { reportApi, questionSetApi, sessionApi, practiceApi } from '@/api'
import { useFlowStore } from '@/store/flow'

const route = useRoute()
const router = useRouter()
const flow = useFlowStore()
const loading = ref(false)
const report = ref(null)
const expandedQ = ref(null)     // 当前展开逐题分析的问题 id
const showRef = ref(true)       // 参考答案展开态
const practicing = ref(null)    // 正在创建针对性练习的题目 id
const practicingAll = ref(false) // 正在一键创建薄弱题型练习
const sessionErrors = []        // 训练开练失败的提示（留作占位）

function toggleQ(id) {
  expandedQ.value = expandedQ.value === id ? null : id
  showRef.value = true
}

const doneCount = computed(() => report.value?.questions?.filter(q => q.total_score != null).length || 0)
const weakQuestionsInReport = computed(() =>
  (report.value?.questions || [])
    .filter(q => q.total_score != null && q.total_score < 70)
    .sort((a, b) => (a.total_score || 0) - (b.total_score || 0))
)
const lastDeltaText = computed(() => {
  const d = report.value?.comparison?.last_delta || 0
  return d >= 0 ? `+${d.toFixed(1)}` : d.toFixed(1)
})
const lastDeltaClass = computed(() => {
  const d = report.value?.comparison?.last_delta || 0
  return d >= 0 ? 'success' : 'warning'
})

function scoreColor(s) {
  if (s == null) return ''
  if (s >= 80) return 'var(--success)'
  if (s >= 70) return ''
  return 'var(--warning)'
}
function fmtMs(ms) {
  if (!ms) return '-'
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
function fmtTs(ms) {
  const s = Math.floor(ms / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
function recLabel(kind) {
  return { improve: '改进', practice: '加练', review: '复盘' }[kind] || kind
}
function recTagClass(kind) {
  return { improve: 'orange', practice: 'green', review: 'blue' }[kind] || ''
}

// 针对薄弱维度加练：调后端 get_weak_points → start_category_session
async function practiceWeak() {
  practicingAll.value = true
  try {
    const weak = await practiceApi.weakPoints()
    const focus = (weak?.focus || [])[0] || (weak?.categories || []).find(c => c.level === 'weak' && c.can_practice)
    if (!focus) {
      message.info('本场薄弱题型暂无可练的专项，先去看逐题回放或者上传一份简历让系统更懂你。')
      router.push('/special')
      return
    }
    const res = await practiceApi.startCategory({
      category: focus.name,
      form_type: 'structured',
      count: 5,
      use_resume: focus.practice_mode === 'resume',
    })
    if (res?.session_id) {
      message.success(`已组建「${focus.name}」针对性训练（${res.session_id}）`)
      flow.setSession(res.session_id)
      router.push(`/answer/${res.session_id}`)
    }
  } catch (e) {
    message.error('开练失败：' + (e?.message || '请稍后再试'))
    router.push('/special')
  } finally {
    practicingAll.value = false
  }
}

// 针对答得不好的题型再练一轮：直接走后端针对性训练接口
async function practiceCategory(q) {
  practicing.value = q.session_question_id
  try {
    const cat = q.category || q.dimension || ''
    if (!cat) {
      router.push('/special')
      return
    }
    const res = await practiceApi.startCategory({
      category: cat,
      form_type: 'structured',
      count: 5,
      use_resume: q.source === 'resume' || q.category === '简历深挖',
    })
    if (res?.session_id) {
      message.success(`已组建「${cat}」针对性训练`)
      flow.setSession(res.session_id)
      router.push(`/answer/${res.session_id}`)
    }
  } catch (e) {
    message.error('开练失败：' + (e?.message || '请稍后再试'))
    router.push('/special')
  } finally {
    practicing.value = null
  }
}

async function startSpecialPractice(name, q) {
  // 兼容旧调用路径：用 startCategory 替代旧的「找题库」逻辑
  await practiceCategory({ category: name, dimension: name, source: q?.source || 'bank' })
}

async function load() {
  const id = Number(route.params.reportId || flow.reportId)
  if (!id) return
  loading.value = true
  try {
    report.value = await reportApi.detail(id)
  } catch (e) {
    report.value = null
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.report-hero { display: grid; grid-template-columns: 1fr 1.4fr; gap: 16px; margin-bottom: 16px; }
.score-card { padding: 28px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; }
.score-label { font-size: 13px; color: var(--text-3); }
.summary-card { padding: 24px; display: flex; flex-direction: column; gap: 14px; }
.summary-card h3 { font-size: 18px; margin: 0; }
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.summary-stat { text-align: center; padding: 14px; border-radius: 12px; background: var(--bg); }
.summary-stat .v { font-size: 22px; font-weight: 700; }
.summary-stat .l { font-size: 12px; color: var(--text-3); }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.dim-list { display: flex; flex-direction: column; gap: 14px; }
.report-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 18px; }

.q-list { display: flex; flex-direction: column; gap: 10px; }
.q-item-wrap { border-radius: 12px; }
.q-item {
  display: grid; grid-template-columns: 1fr 60px 80px;
  align-items: center; gap: 14px; padding: 14px 18px;
  border-radius: 12px; background: var(--bg); cursor: pointer;
  transition: background .2s;
}
.q-item:hover { background: var(--primary-soft); }
.q-item .label { font-size: 13px; }
.q-item .label small { display: block; color: var(--text-3); margin-top: 2px; font-size: 11px; }
.q-item .score { font-size: 16px; font-weight: 700; text-align: right; }
.q-item .arrow { text-align: right; color: var(--primary); font-size: 13px; font-weight: 600; }

/* 逐题分析展开区 */
.q-analysis {
  margin-top: 4px; padding: 14px 16px;
  background: #fff; border: 1px solid var(--border-soft); border-radius: 12px;
}
.q-title-line { font-size: 13px; font-weight: 600; line-height: 1.6; margin-bottom: 10px; }
.ana-block { margin-bottom: 10px; }
.ana-title { font-size: 12px; font-weight: 700; margin-bottom: 4px; }
.ana-block.good .ana-title { color: var(--success); }
.ana-block.bad .ana-title { color: var(--warning); }
.ana-block ul { margin: 0; padding-left: 18px; }
.ana-block li { font-size: 12px; color: var(--text-2); line-height: 1.7; }
.ana-block.good li { color: var(--success); }
.ana-block.bad li { color: var(--warning); }
.ref-text {
  margin: 6px 0 0; padding: 10px 12px; border-radius: 8px;
  background: var(--bg); font-size: 12px; line-height: 1.7; color: var(--text-1);
}
.ana-ops { display: flex; gap: 10px; margin-top: 4px; }

.highlight-list, .rec-list { display: flex; flex-direction: column; gap: 10px; }
.highlight-row { display: flex; gap: 12px; padding: 10px 12px; background: var(--bg); border-radius: 10px; }
.highlight-row .ts { color: var(--text-3); font-family: 'Inter', monospace; font-size: 12px; flex-shrink: 0; }
.highlight-row .snippet { font-size: 13px; }
.rec-item { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; background: var(--bg); border-radius: 10px; }
.rec-item .content { font-size: 13px; color: var(--text-1); }

/* 本场薄弱题 */
.weak-grid { display: flex; flex-direction: column; gap: 10px; }
.weak-row {
  display: grid; grid-template-columns: 1fr 50px auto;
  align-items: center; gap: 14px;
  padding: 14px 16px; border-radius: 12px;
  background: #FFFBF0; border: 1px solid #F7D9B6;
}
.weak-meta { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.weak-cat { font-size: 12px; color: var(--warning); font-weight: 600; }
.weak-title { font-size: 13px; color: var(--text-1); line-height: 1.5;
              display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
              overflow: hidden; text-overflow: ellipsis; }
.weak-score { font-size: 22px; font-weight: 700; text-align: center; }

@media (max-width: 1024px) {
  .report-hero, .two-col { grid-template-columns: 1fr; }
}
</style>
