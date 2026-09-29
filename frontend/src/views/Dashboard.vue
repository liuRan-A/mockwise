<template>
  <div class="container">
    <!-- Hero -->
    <div class="hero-card">
      <div>
        <h2 class="hero-title">{{ greeting }}，{{ store.nickname }}</h2>
        <p class="hero-sub">
          本周已练 {{ data.week_count || 0 }} 次 · 综合平均分
          {{ (data.avg_score_30d ?? 0).toFixed(1) }}，超过了 {{ data.percentile || 0 }}% 的同岗位练习者
        </p>
      </div>
      <button class="mw-btn-hero" @click="$router.push('/form')">开始全真模拟 →</button>
    </div>

    <!-- KPI -->
    <div class="kpi-grid">
      <KpiCard label="本月剩余模拟" :value="quotaLeft" unit="次"
               :delta="`额度 ${quotaTotal} / 用掉 ${quotaTotal - quotaLeft}`"
               delta-type="muted" />
      <KpiCard label="连续练习" :value="data.streak_days ?? 0" unit="天"
               delta="坚持就是胜利" delta-type="up" />
      <KpiCard label="综合平均分" :value="(data.avg_score_30d ?? 0).toFixed(1)"
               :delta="(data.last_delta ?? 0) >= 0 ? `↑ 较上场 +${(data.last_delta ?? 0).toFixed(1)}` : `↓ 较上场 ${(data.last_delta ?? 0).toFixed(1)}`"
               :delta-type="(data.last_delta ?? 0) >= 0 ? 'up' : 'down'" />
      <KpiCard label="最优得分" :value="data.best_score ? Math.round(data.best_score) : 0"
               delta="历史最佳" delta-type="muted" />
    </div>

    <!-- 趋势 + 推荐 -->
    <div class="two-col">
      <div class="mw-card">
        <h3>综合得分趋势（最近 {{ trend.length }} 场）</h3>
        <div ref="trendRef" class="trend-chart"></div>
        <a-empty v-if="!trend.length" description="暂无练习记录" style="margin-top:40px" />
      </div>

      <div class="mw-card">
        <h3>今日推荐练习</h3>
        <div class="rec-list">
          <div v-for="r in recommend" :key="r.set_id" class="rec-row" @click="quickStart(r)">
            <span class="name">{{ r.name }}</span>
            <span class="match">适配度 {{ Math.round(r.match_score) }}%</span>
          </div>
          <a-empty v-if="!recommend.length" description="暂无推荐" />
        </div>
      </div>
    </div>

    <!-- 历史 -->
    <div class="mw-card" style="margin-top:16px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="margin:0;">最近练习</h3>
        <a-button type="link" @click="$router.push('/history')">查看全部 ›</a-button>
      </div>
      <div class="history-list">
        <div
          v-for="h in history" :key="h.session_id"
          class="history-row" :class="{ clickable: h.session_id }"
          @click="openHistory(h)"
        >
          <div class="name">{{ h.set_name }}</div>
          <div class="bar"><span :style="{ width: barWidth(h.total_score) }"></span></div>
          <div class="score">{{ (h.total_score ?? 0).toFixed(1) }}</div>
          <div class="date">{{ fmt(h.practiced_at) }}</div>
        </div>
        <a-empty v-if="!history.length" description="还没有练习记录，点击右上角开始第一场" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useUserStore } from '@/store/user'
import { useFlowStore } from '@/store/flow'
import { dashboardApi, questionSetApi, sessionApi, reportApi } from '@/api'
import { message } from 'ant-design-vue'
import KpiCard from '@/components/KpiCard.vue'

const router = useRouter()
const store = useUserStore()
const flow = useFlowStore()

const data = ref({})
const trend = ref([])
const recommend = ref([])
const history = ref([])
const trendRef = ref(null)
let chart = null

const greeting = (() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})()

// 配额以 store.quota 为单一可信源（充值后由 MainLayout 的 onRecharged 即时刷新），
// 登录/配额未加载时回退到 dashboard 聚合数据，避免空白闪烁。
const quotaLeft = computed(() => store.quota?.simulated_left ?? data.value.simulated_left ?? 0)
const quotaTotal = computed(() => store.quota?.simulated_total ?? data.value.simulated_total ?? 0)

function barWidth(score) { return `${Math.max(5, Math.min(100, score))}%` }
function fmt(s) { return (s || '').slice(5, 16) }

async function load() {
  try {
    const [d, t, r, h] = await Promise.all([
      dashboardApi.get(), dashboardApi.trend(5), dashboardApi.recommend(3), dashboardApi.history(5),
    ])
    data.value = d || {}
    trend.value = t || []
    recommend.value = r || []
    history.value = h || []
    await nextTick()
    renderChart()
  } catch (e) { /* 静默 */ }
}

function renderChart() {
  if (!trendRef.value || !trend.value.length) return
  if (!chart) chart = echarts.init(trendRef.value)
  chart.setOption({
    grid: { left: 30, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category', data: trend.value.map(t => fmt(t.practiced_at)),
      axisLine: { lineStyle: { color: '#E3E6EE' } }, axisTick: { show: false },
      axisLabel: { color: '#8A90A0', fontSize: 11 },
    },
    yAxis: { type: 'value', min: 50, max: 100, splitLine: { lineStyle: { color: '#F0F1F5' } }, axisLabel: { color: '#8A90A0', fontSize: 11 } },
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>得分：${p[0].value}` },
    series: [{
      type: 'line', smooth: true, symbol: 'circle', symbolSize: 8,
      data: trend.value.map(t => Number(t.score.toFixed(1))),
      lineStyle: { color: '#3E63DD', width: 3 }, itemStyle: { color: '#3E63DD', borderColor: '#fff', borderWidth: 2 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(62,99,221,.2)' }, { offset: 1, color: 'rgba(62,99,221,0)' },
      ]) },
    }],
  })
}

async function quickStart(rec) {
  try {
    const setDetail = await questionSetApi.detail(rec.set_id)
    // 学情推荐的薄弱项专项套题：直接创建专项练习场次并进入作答
    if (setDetail.industry === '专项练习') {
      const res = await sessionApi.create({
        set_id: rec.set_id, form_type: 'structured',
        voice_mode: 'voice', difficulty: 'medium',
        enable_followup: true, peer_count: 0,
      })
      flow.setSession(res.session_id)
      router.push(`/answer/${res.session_id}`)
    } else {
      flow.setForm('structured')
      flow.setSet(setDetail)
      router.push('/set')
    }
  } catch (e) { /* */ }
}

async function openHistory(h) {
  if (!h.session_id) return
  try {
    const r = await reportApi.bySession(h.session_id)
    if (r?.report_id) router.push(`/report/${r.report_id}`)
  } catch (e) { /* 未完成的场次无报告 */ }
}

onMounted(load)
</script>

<style scoped>
.hero-card {
  background: linear-gradient(135deg, var(--primary) 0%, #5B7FE8 100%);
  color: #fff; border-radius: var(--r-card);
  padding: 28px 32px; display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.hero-title { font-size: 22px; font-weight: 700; margin: 0; }
.hero-sub { margin: 6px 0 0; opacity: .85; font-size: 13px; }

.kpi-grid { display: grid; gap: 16px; grid-template-columns: repeat(4, 1fr); margin-bottom: 20px; }
.two-col { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; }
.trend-chart { width: 100%; height: 220px; }

.rec-list { display: flex; flex-direction: column; gap: 10px; }
.rec-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border-radius: 12px; background: var(--bg); cursor: pointer;
  transition: background .2s;
}
.rec-row:hover { background: var(--primary-soft); }
.rec-row .name { font-size: 13px; color: var(--text-2); flex: 1; }
.rec-row .match { font-size: 12px; color: var(--success); font-weight: 600; }

.history-list { display: flex; flex-direction: column; gap: 10px; }
.history-row {
  display: grid; grid-template-columns: 1fr 1fr 60px 90px;
  align-items: center; gap: 12px;
  padding: 10px 14px; border-radius: 12px; background: var(--bg);
}
.history-row.clickable { cursor: pointer; transition: background .2s; }
.history-row.clickable:hover { background: var(--primary-soft); }
.history-row .name { font-size: 13px; font-weight: 600; }
.history-row .bar { height: 8px; border-radius: 4px; background: var(--border-soft); position: relative; overflow: hidden; }
.history-row .bar > span { position: absolute; left: 0; top: 0; bottom: 0; background: var(--primary); border-radius: 4px; }
.history-row .score { font-size: 13px; font-weight: 700; text-align: right; }
.history-row .date { font-size: 12px; color: var(--text-3); text-align: right; }

@media (max-width: 1024px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
</style>
