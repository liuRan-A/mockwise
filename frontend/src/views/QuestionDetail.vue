<template>
  <div class="container">
    <a-page-header
      :title="`第 ${detail?.seq || '?'} 题 · ${detail?.question_category || ''}`"
      sub-title="逐题详情 / 回放"
      @back="$router.back()"
      style="padding: 0 0 16px;"
    />

    <a-spin :spinning="loading">
      <template v-if="detail">
        <div class="two-col">
          <!-- 左：题干 + 回放 + 转写 -->
          <div>
            <div class="mw-card q-card" style="margin-bottom:16px;">
              <span class="mw-tag blue q-tag" style="align-self:flex-start;">
                {{ detail.question_dimension || '考察维度' }}
              </span>
              <div class="q-title">{{ detail.question_content }}</div>
              <div class="q-meta">
                来源：{{ sourceLabel }} · 建议作答时长 {{ Math.round(detail.time_limit_s / 60) }} 分钟
              </div>
            </div>

            <div class="mw-card" style="margin-bottom:16px;">
              <h3>视频回放</h3>
              <div class="player">
                <div class="player-mask">
                  <PlayCircleOutlined style="font-size:48px; color:#fff;" />
                  <div class="player-meta">{{ fmtMs(detail.duration_ms) }} · 倍速 1.0x</div>
                </div>
              </div>
              <div class="speed-row">
                <a-radio-group v-model:value="speed" button-style="solid" size="small">
                  <a-radio-button value="0.5">0.5x</a-radio-button>
                  <a-radio-button value="1">1x</a-radio-button>
                  <a-radio-button value="1.5">1.5x</a-radio-button>
                  <a-radio-button value="2">2x</a-radio-button>
                </a-radio-group>
              </div>
            </div>

            <div class="mw-card">
              <h3>转写全文</h3>
              <div class="transcript">
                <div v-for="(line, i) in transcriptLines" :key="i" class="transcript-line">
                  <span class="ts">{{ String(i + 1).padStart(2, '0') }}</span>
                  <span>{{ line }}</span>
                </div>
                <a-empty v-if="!transcriptLines.length" description="无转写记录" />
              </div>
            </div>
          </div>

          <!-- 右：评分 + 客观指标 + 答题分析 + 参考答案 -->
          <div>
            <div class="mw-card" style="margin-bottom:16px;">
              <h3>分维度评分</h3>
              <div class="dim-list">
                <DimensionBar
                  v-for="s in (detail.scores || [])"
                  :key="s.dimension"
                  :name="s.dimension" :score="s.score"
                />
              </div>
              <div class="total-row">
                <span>本题得分</span>
                <span class="total" :style="{ color: scoreColor(detail.total_score) }">
                  {{ detail.total_score ? Math.round(detail.total_score) : '-' }}
                </span>
              </div>
            </div>

            <div class="mw-card" style="margin-bottom:16px;" v-if="detail.metrics && hasRealMetric(detail.metrics)">
              <h3>客观指标</h3>
              <div class="metric-row"><span>语速</span><b>{{ detail.metrics.wpm }} 字/min</b></div>
              <div class="metric-row"><span>停顿次数</span><b>{{ detail.metrics.pause_count }} 次</b></div>
              <div class="metric-row"><span>停顿时长</span><b>{{ fmtMs(detail.metrics.pause_ms_total) }}</b></div>
              <div class="metric-row"><span>口头禅</span><b>{{ detail.metrics.filler_count }} 次</b></div>
            </div>

            <!-- 答题分析：答得好 / 答得欠缺 -->
            <div class="mw-card" style="margin-bottom:16px;">
              <h3>答题分析</h3>
              <div class="grid-2">
                <div class="cell good">
                  <div class="cell-title">
                    <span class="mw-tag green">答得好的地方</span>
                    <span class="cell-count">{{ (detail.strengths || []).length }}</span>
                  </div>
                  <ul v-if="(detail.strengths || []).length">
                    <li v-for="(s, i) in detail.strengths" :key="i">
                      <CheckCircleFilled class="bullet" />
                      <div class="point-block">
                        <div class="point-text">{{ ptText(s) }}</div>
                        <div v-if="ptQuote(s)" class="point-quote">"{{ ptQuote(s) }}"</div>
                      </div>
                    </li>
                  </ul>
                  <a-empty v-else :image-style="{ height: '60px' }" description="暂无突出亮点" />
                </div>
                <div class="cell bad">
                  <div class="cell-title">
                    <span class="mw-tag orange">答得欠缺的地方</span>
                    <span class="cell-count">{{ (detail.gaps || []).length }}</span>
                  </div>
                  <ul v-if="(detail.gaps || []).length">
                    <li v-for="(g, i) in detail.gaps" :key="i">
                      <CloseCircleFilled class="bullet" />
                      <div class="point-block">
                        <div class="point-text">{{ ptText(g) }}</div>
                        <div v-if="ptWhy(g)" class="point-why">原因：{{ ptWhy(g) }}</div>
                        <div v-if="ptHow(g)" class="point-how">改进：{{ ptHow(g) }}</div>
                      </div>
                    </li>
                  </ul>
                  <a-empty v-else :image-style="{ height: '60px' }" description="暂无明显短板" />
                </div>
              </div>
              <!-- 兜底：若 strengths/gaps 都没生成，从旧 recommendations/highlights 提一些 -->
              <div class="legacy-block" v-if="!hasStructuredAnalysis">
                <template v-if="(detail.highlights || []).length">
                  <div class="legacy-title">高光时刻</div>
                  <div class="highlight-list">
                    <div v-for="(h, i) in detail.highlights" :key="'h'+i" class="highlight-row">
                      <span class="ts">{{ fmtTs(h.ts_ms) }}</span>
                      <span class="snippet">{{ h.snippet }}</span>
                    </div>
                  </div>
                </template>
                <template v-if="(detail.recommendations || []).length">
                  <div class="legacy-title" style="margin-top:12px;">改进建议</div>
                  <div class="rec-list">
                    <div v-for="(r, i) in detail.recommendations" :key="'r'+i" class="rec-item">
                      <span class="mw-tag orange">建议</span>
                      <span class="content">{{ r.content }}</span>
                    </div>
                  </div>
                </template>
              </div>
            </div>

            <!-- 参考答案（结构化） -->
            <div class="mw-card">
              <h3>参考答案</h3>
              <template v-if="refDetail">
                <div class="ref-section">
                  <div class="ref-section-title">采分点</div>
                  <div class="ref-points">
                    <span v-for="(p, i) in (refDetail.key_points || [])" :key="i" class="ref-point">
                      {{ p }}
                    </span>
                  </div>
                </div>
                <div class="ref-section" v-if="(refDetail.outline || []).length">
                  <div class="ref-section-title">答题框架</div>
                  <ol class="ref-outline">
                    <li v-for="(o, i) in refDetail.outline" :key="i">{{ o }}</li>
                  </ol>
                </div>
                <div class="ref-section" v-if="refDetail.sample">
                  <div class="ref-section-title">示范作答</div>
                  <div class="ref-sample">{{ refDetail.sample }}</div>
                </div>
                <div class="ref-section" v-if="(refDetail.common_traps || []).length">
                  <div class="ref-section-title">常见雷区</div>
                  <ul class="ref-traps">
                    <li v-for="(t, i) in refDetail.common_traps" :key="i">{{ t }}</li>
                  </ul>
                </div>
              </template>
              <template v-else-if="detail.ref_answer">
                <div class="ref-sample">{{ detail.ref_answer }}</div>
              </template>
              <a-empty v-else description="此题暂无参考答案，可点击底部「针对此题再练一次」强化学习" />
            </div>
          </div>
        </div>

        <!-- 底部：针对此题再练一次（薄弱题针对性训练入口） -->
        <div class="bottom-bar">
          <div class="bar-inner">
            <div class="bar-tip">
              这道题答得不理想？想立刻巩固同类题？
            </div>
            <a-space>
              <a-button @click="$router.back()">返回报告</a-button>
              <a-button type="primary" :loading="retrying" @click="retrySameCategory">
                针对此题所在题型再来一轮
              </a-button>
            </a-space>
          </div>
        </div>
      </template>
    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PlayCircleOutlined, CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons-vue'
import DimensionBar from '@/components/DimensionBar.vue'
import { sessionApi, practiceApi } from '@/api'
import { message } from 'ant-design-vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const retrying = ref(false)
const detail = ref(null)
const speed = ref('1')

const transcriptLines = computed(() => {
  if (!detail.value?.transcript) return []
  return detail.value.transcript.split('\n').filter(s => s.trim())
})

const refDetail = computed(() => {
  const rd = detail.value?.ref_detail
  if (!rd) return null
  // 兼容后端把 ref_detail 存成 JSON 字符串的情况
  if (typeof rd === 'string') {
    try { return JSON.parse(rd) } catch { return null }
  }
  return rd
})

const sourceLabel = computed(() => {
  if (detail.value?.source === 'resume') return '简历深挖 · 由你的简历动态生成'
  return '题库选题'
})

const hasStructuredAnalysis = computed(() =>
  (detail.value?.strengths || []).length > 0 || (detail.value?.gaps || []).length > 0
)

function ptText(x) {
  if (x == null) return ''
  if (typeof x === 'string') return x
  return x.point || x.text || x.content || ''
}
function ptQuote(x) {
  if (!x || typeof x === 'string') return ''
  return x.quote || ''
}
function ptWhy(x) {
  if (!x || typeof x === 'string') return ''
  return x.why || x.reason || ''
}
function ptHow(x) {
  if (!x || typeof x === 'string') return ''
  return x.how || x.suggestion || x.fix || ''
}
function hasRealMetric(m) {
  return m && (m.wpm || m.pause_count || m.pause_ms_total || m.filler_count)
}
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
  if (ms == null) return '--:--'
  const s = Math.floor(ms / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

async function retrySameCategory() {
  const cat = detail.value?.question_category
  if (!cat) {
    message.warning('当前题型不可识别')
    return
  }
  retrying.value = true
  try {
    const res = await practiceApi.startCategory({
      category: cat,
      form_type: detail.value?.source === 'resume' ? 'structured' : 'structured',
      count: 5,
      use_resume: detail.value?.source === 'resume' || !!detail.value?.has_resume,
    })
    if (res?.session_id) {
      message.success(`已为你组建一场「${cat}」针对性训练`)
      router.push({ name: 'answerById', params: { sessionId: res.session_id } })
    }
  } catch (e) {
    message.error('开练失败：' + (e?.message || '请稍后再试'))
  } finally {
    retrying.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    detail.value = await sessionApi.questionDetail(
      Number(route.params.sessionId),
      Number(route.params.sqId),
    )
  } catch (e) {
    detail.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.two-col { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }
.q-card { display: flex; flex-direction: column; gap: 14px; padding: 22px; }
.q-tag { align-self: flex-start; }
.q-title { font-size: 15px; font-weight: 600; line-height: 1.6; }
.q-meta { font-size: 12px; color: var(--text-3); }

.player {
  height: 220px; border-radius: 12px; background: #1B2030;
  display: flex; align-items: center; justify-content: center; position: relative;
  cursor: pointer;
}
.player-mask { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.player-meta { color: rgba(255,255,255,.85); font-size: 12px; }
.speed-row { margin-top: 12px; display: flex; justify-content: flex-end; }

.transcript { max-height: 320px; overflow-y: auto; }
.transcript-line {
  font-size: 13px; padding: 8px 0; color: var(--text-1);
  border-bottom: 1px dashed var(--border-soft);
  display: flex; gap: 12px;
}
.transcript-line:last-child { border-bottom: none; }
.transcript-line .ts { color: var(--text-3); font-family: 'Inter', monospace; font-size: 12px; min-width: 24px; }

.dim-list { display: flex; flex-direction: column; gap: 14px; }
.total-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--border-soft);
}
.total-row .total { font-size: 24px; font-weight: 700; }

.metric-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--border-soft); }
.metric-row:last-child { border-bottom: none; }
.metric-row span { font-size: 13px; color: var(--text-2); }
.metric-row b { font-size: 13px; }

/* 答题分析：左右两栏对照 */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.cell { border-radius: 10px; padding: 12px 14px; min-height: 110px; }
.cell.good { background: #ECF8F1; border: 1px solid #D1ECDD; }
.cell.bad  { background: #FFF6EC; border: 1px solid #F7D9B6; }
.cell-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cell-count { font-size: 12px; color: var(--text-3); }
.cell ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.cell li { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; line-height: 1.55; color: var(--text-1); }
.cell .bullet { flex-shrink: 0; margin-top: 3px; font-size: 14px; }
.cell.good .bullet { color: var(--success); }
.cell.bad  .bullet { color: var(--warning); }
.point-block { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.point-text { font-size: 13px; line-height: 1.55; color: var(--text-1); }
.point-quote { font-size: 12px; color: #4D6B58; padding-left: 8px; border-left: 2px solid #B7DDC4; }
.point-why { font-size: 12px; color: #8B6A3D; }
.point-how { font-size: 12px; color: #2B4F8A; background: #EAF1FB; padding: 4px 8px; border-radius: 6px; }

/* 兜底高光/建议 */
.legacy-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.highlight-list, .rec-list { display: flex; flex-direction: column; gap: 8px; }
.highlight-row { display: flex; gap: 12px; padding: 8px 12px; background: #F7F8FA; border-radius: 8px; }
.highlight-row .ts { color: var(--text-3); font-family: 'Inter', monospace; font-size: 12px; flex-shrink: 0; }
.highlight-row .snippet { font-size: 13px; }
.rec-item { display: flex; gap: 10px; align-items: flex-start; padding: 8px 12px; background: #F7F8FA; border-radius: 8px; }
.rec-item .content { font-size: 13px; }

/* 参考答案 */
.ref-section { margin-bottom: 14px; }
.ref-section:last-child { margin-bottom: 0; }
.ref-section-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text-2); }
.ref-points { display: flex; flex-wrap: wrap; gap: 8px; }
.ref-point {
  font-size: 12.5px; line-height: 1.4; padding: 6px 12px;
  background: #EAF1FB; color: #2B4F8A; border-radius: 16px;
  border: 1px solid #D7E4F7;
}
.ref-outline { padding-left: 22px; margin: 0; }
.ref-outline li { font-size: 13px; line-height: 1.7; color: var(--text-1); }
.ref-sample {
  font-size: 13px; line-height: 1.75; padding: 14px 16px;
  background: #F7F8FA; border-radius: 10px; color: var(--text-1);
  white-space: pre-wrap;
}
.ref-traps { padding-left: 22px; margin: 0; }
.ref-traps li { font-size: 13px; line-height: 1.7; color: #B05A12; }

/* 底部动作条 */
.bottom-bar {
  margin-top: 20px;
  background: #FFFBF0;
  border: 1px solid #F7D9B6;
  border-radius: 12px;
  padding: 14px 20px;
}
.bar-inner { display: flex; justify-content: space-between; align-items: center; }
.bar-tip { font-size: 14px; color: #5C3D0E; }

@media (max-width: 1024px) {
  .two-col { grid-template-columns: 1fr; }
  .grid-2 { grid-template-columns: 1fr; }
  .bar-inner { flex-direction: column; gap: 12px; }
}
</style>
