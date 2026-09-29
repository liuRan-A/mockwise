<template>
  <div class="container">
    <h2 class="section-title">练习历史</h2>
    <p class="section-sub">所有完成场次一览，点击右侧分数进入对应报告。</p>

    <a-spin :spinning="loading">
      <div class="mw-card">
        <div class="history-list">
          <div
            v-for="(h, i) in list" :key="i"
            class="history-row"
            :class="{ clickable: h.session_id }"
            @click="openReport(h)"
          >
            <div class="seq">#{{ list.length - i }}</div>
            <div class="name">{{ h.set_name }}</div>
            <div class="bar"><span :style="{ width: barWidth(h.total_score) }"></span></div>
            <div class="score" :style="{ color: scoreColor(h.total_score) }">{{ h.total_score.toFixed(1) }}</div>
            <div class="date">{{ fmt(h.practiced_at) }}</div>
          </div>
          <a-empty v-if="!list.length" description="还没有练习记录" />
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { dashboardApi, reportApi } from '@/api'

const router = useRouter()
const loading = ref(false)
const list = ref([])

function barWidth(s) { return `${Math.max(5, Math.min(100, s))}%` }
function scoreColor(s) {
  if (s >= 80) return 'var(--success)'
  if (s >= 70) return ''
  return 'var(--warning)'
}
function fmt(s) { return (s || '').slice(0, 16) }

async function openReport(h) {
  if (!h.session_id) return
  try {
    const r = await reportApi.bySession(h.session_id)
    if (r?.report_id) router.push(`/report/${r.report_id}`)
    else message.warning('该场练习暂未生成报告')
  } catch (e) {
    message.warning('该场练习暂未生成报告')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    list.value = await dashboardApi.history(50)
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.history-list { display: flex; flex-direction: column; gap: 10px; }
.history-row {
  display: grid; grid-template-columns: 50px 1fr 1fr 60px 130px;
  align-items: center; gap: 12px; padding: 12px 16px;
  border-radius: 12px; background: var(--bg);
}
.history-row.clickable { cursor: pointer; transition: background .2s; }
.history-row.clickable:hover { background: var(--primary-soft); }
.history-row .seq { font-size: 13px; color: var(--text-3); font-weight: 600; }
.history-row .name { font-size: 13px; font-weight: 600; }
.history-row .bar { height: 8px; border-radius: 4px; background: var(--border-soft); position: relative; overflow: hidden; }
.history-row .bar > span { position: absolute; left: 0; top: 0; bottom: 0; background: var(--primary); border-radius: 4px; }
.history-row .score { font-size: 14px; font-weight: 700; text-align: right; }
.history-row .date { font-size: 12px; color: var(--text-3); text-align: right; }
</style>
