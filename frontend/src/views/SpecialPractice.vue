<template>
  <div class="container">
    <h2 class="section-title">专项练习</h2>
    <p class="section-sub">针对单一能力维度集中训练，每套 4～6 题，作答后即时评分与复盘。点击「去练习」直接开始。</p>

    <!-- 我的薄弱题型（来自历史数据；新用户会显示空态引导） -->
    <div class="mw-card weak-card" v-if="weakPoints && weakPoints.has_data">
      <div class="weak-head">
        <h3>根据你的练习历史，AI 识别出这些薄弱题型</h3>
        <a-button size="small" @click="loadWeakPoints">刷新</a-button>
      </div>
      <p class="weak-tip">
        点击「针对练习」会按这个题型实时组一场 5 题训练（含同题型选题，有简历时混入 1-2 道简历深挖题）。
      </p>
      <div class="weak-list">
        <div v-for="(c, i) in weakPoints.categories.filter(x => x.level !== 'good').slice(0, 6)"
             :key="i"
             class="weak-row"
             :class="'level-' + c.level"
        >
          <div class="weak-cat">
            <div class="cw-cat-name">{{ c.name }}</div>
            <div class="cw-cat-meta">{{ c.count }} 题 · {{ c.level === 'weak' ? '薄弱' : '中等' }}</div>
          </div>
          <div class="weak-avg">
            <div class="cw-avg-score">{{ c.avg_score }}</div>
            <div class="cw-avg-label">平均分</div>
          </div>
          <div class="weak-action">
            <a-button type="primary" ghost :loading="startingFocus === c.name" @click="startFocus(c)">
              针对练习 →
            </a-button>
            <div class="weak-mode">{{ practiceModeLabel(c.practice_mode) }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="mw-card weak-empty" v-else-if="weakPoints && !weakPoints.has_data">
      <div class="empty-row">
        <span class="empty-emoji">📊</span>
        <div>
          <h3 style="margin:0 0 4px;">还没有足够的练习数据</h3>
          <p style="margin:0; color:var(--text-3); font-size:13px;">
            先完成一场完整模拟，系统会基于你每道题的得分识别薄弱题型，并给出针对性的训练建议。
          </p>
        </div>
      </div>
    </div>

    <h3 class="block-title">选题库练习</h3>

    <a-spin :spinning="loading">
      <div v-if="groups.length" class="sp-grid">
        <div v-for="g in groups" :key="g.category" class="sp-card">
          <div class="sp-head">
            <div class="sp-icon" :style="{ background: g.color + '1A', color: g.color }">{{ g.category.slice(0, 1) }}</div>
            <div>
              <h4 class="sp-name">{{ g.category }}</h4>
              <div class="sp-meta">{{ g.questionCount }} 题 · 约 {{ g.minutes }} 分钟</div>
            </div>
          </div>
          <p class="sp-desc">{{ g.description }}</p>
          <div class="sp-foot">
            <span class="mw-tag blue">{{ g.setName }}</span>
            <a-button type="primary" :loading="startingId === g.setId" @click="start(g)">去练习 →</a-button>
          </div>
        </div>
      </div>
      <a-empty v-else-if="!loading" description="暂无专项题库" />
    </a-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { questionSetApi, sessionApi, practiceApi } from '@/api'
import { useFlowStore } from '@/store/flow'

const router = useRouter()
const flow = useFlowStore()

const loading = ref(false)
const startingId = ref(null)
const startingFocus = ref(null)
const sets = ref([])
const weakPoints = ref(null)

const COLORS = ['#3E63DD', '#E8912D', '#2FA36B', '#7C6BD6', '#D8504F', '#0E9AA7']

const groups = computed(() =>
  sets.value.map((s, i) => ({
    setId: s.id,
    setName: s.name,
    category: s.position_type || '综合',
    description: s.description,
    questionCount: s.question_count || 0,
    minutes: s.est_minutes || 15,
    color: COLORS[i % COLORS.length],
  }))
)

function practiceModeLabel(mode) {
  return {
    set: '套题训练',
    category: '同题型组题',
    resume: '简历动态题',
  }[mode] || ''
}

async function loadWeakPoints() {
  try {
    weakPoints.value = await practiceApi.weakPoints()
  } catch (e) {
    weakPoints.value = null
  }
}

async function start(g) {
  startingId.value = g.setId
  try {
    const res = await sessionApi.create({
      set_id: g.setId,
      form_type: 'structured',
      voice_mode: 'voice',
      difficulty: 'medium',
      enable_followup: true,
      peer_count: 0,
    })
    flow.setSession(res.session_id)
    message.success(`已开始「${g.category}」专项练习`)
    router.push(`/answer/${res.session_id}`)
  } catch (e) { /* http 拦截器已提示 */ }
  finally { startingId.value = null }
}

async function startFocus(c) {
  startingFocus.value = c.name
  try {
    const res = await practiceApi.startCategory({
      category: c.name,
      form_type: 'structured',
      count: 5,
      use_resume: c.practice_mode === 'resume',
    })
    if (res?.session_id) {
      message.success(`已为「${c.name}」组建一场针对性训练`)
      flow.setSession(res.session_id)
      router.push(`/answer/${res.session_id}`)
    }
  } catch (e) {
    message.error('开练失败：' + (e?.message || '请稍后再试'))
  } finally {
    startingFocus.value = null
  }
}

onMounted(async () => {
  loading.value = true
  Promise.all([
    loadWeakPoints(),
    (async () => {
      try {
        const all = await questionSetApi.list()
        sets.value = (all || []).filter(s => s.industry === '专项练习')
      } catch (e) {
        sets.value = []
      }
    })(),
  ]).finally(() => { loading.value = false })
})
</script>

<style scoped>
.block-title { font-size: 16px; font-weight: 700; margin: 24px 0 12px; }

/* 薄弱题型 */
.weak-card { padding: 20px 24px; margin-bottom: 18px; }
.weak-head { display: flex; justify-content: space-between; align-items: center; }
.weak-head h3 { margin: 0; font-size: 16px; }
.weak-tip { color: var(--text-3); font-size: 12.5px; margin: 8px 0 16px; }
.weak-list { display: flex; flex-direction: column; gap: 10px; }
.weak-row {
  display: grid; grid-template-columns: 1fr 90px auto; gap: 16px;
  align-items: center; padding: 14px 18px; border-radius: 12px;
}
.level-weak { background: #FFFBF0; border: 1px solid #F7D9B6; }
.level-medium { background: #F7FAFE; border: 1px solid #D7E4F7; }
.cw-cat-name { font-size: 14px; font-weight: 600; }
.cw-cat-meta { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.cw-avg-score { font-size: 22px; font-weight: 700; text-align: center; }
.cw-avg-label { font-size: 11px; color: var(--text-3); text-align: center; }
.weak-action { display: flex; flex-direction: column; gap: 6px; align-items: stretch; }
.weak-mode { font-size: 11px; color: var(--text-3); text-align: center; }

/* 空态 */
.weak-empty { padding: 20px 24px; margin-bottom: 18px; background: linear-gradient(135deg,#F7FAFE 0%, #FAFCFF 100%); }
.empty-row { display: flex; gap: 14px; align-items: center; }
.empty-emoji { font-size: 32px; }

.sp-grid { display: grid; gap: 20px; grid-template-columns: repeat(3, 1fr); }
.sp-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--r-card); padding: 22px;
  display: flex; flex-direction: column; gap: 14px;
  transition: all .2s;
}
.sp-card:hover { border-color: var(--primary); box-shadow: var(--shadow-md); transform: translateY(-2px); }
.sp-head { display: flex; align-items: center; gap: 12px; }
.sp-icon {
  width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700;
}
.sp-name { margin: 0; font-size: 16px; font-weight: 700; }
.sp-meta { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.sp-desc { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.6; flex: 1; }
.sp-foot { display: flex; justify-content: space-between; align-items: center; }

@media (max-width: 1100px) { .sp-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 720px) {
  .sp-grid { grid-template-columns: 1fr; }
  .weak-row { grid-template-columns: 1fr 70px; row-gap: 10px; }
  .weak-action { grid-column: 1 / -1; }
}
</style>
