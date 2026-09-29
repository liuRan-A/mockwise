<template>
  <div class="container">
    <StepsIndicator :current="1" />

    <h2 class="section-title">选择面试形式</h2>
    <p class="section-sub">不同形式对应不同的考核维度、作答体验与群面互动。我们会按你的选择进入下一屏。</p>

    <div class="form-grid">
      <div
        v-for="f in forms"
        :key="f.key"
        class="opt-card"
        :class="{ active: flow.formType === f.key }"
        @click="select(f.key)"
      >
        <div class="ico" v-html="f.icon"></div>
        <h4>{{ f.title }}</h4>
        <p>{{ f.desc }}</p>
        <div class="meta">
          <span>题目数 <b>{{ f.qRange }}</b></span>
          <span>预计用时 <b>{{ f.tRange }}</b></span>
          <span>已练 <b>{{ practicedCount(f.key) }}</b> 次</span>
        </div>
      </div>
    </div>

    <div class="action-bar">
      <a-button size="large" @click="saveFavorite">保存为我的常用</a-button>
      <a-button type="primary" size="large" @click="next">下一步：选择套题 →</a-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import StepsIndicator from '@/components/StepsIndicator.vue'
import { useFlowStore } from '@/store/flow'
import { dashboardApi } from '@/api'

const router = useRouter()
const flow = useFlowStore()
const stats = ref([])

const forms = [
  {
    key: 'structured', title: '结构化面试',
    desc: '1 对 1 与 AI 面试官对话，单题思考 60s + 作答 180s，自动进入下一题。',
    qRange: '5-10', tRange: '20-30 min',
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="14" height="12" rx="2" fill="#3E63DD"/><rect x="7" y="8" width="14" height="12" rx="2" fill="#7C6BD6"/></svg>',
  },
  {
    key: 'group', title: '无领导小组讨论',
    desc: '6 人同场 18 分钟，分为「个人陈述 → 自由讨论 → 总结陈词」三阶段，需举手抢发言权。',
    qRange: '6', tRange: '18-22 min',
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="8" cy="8" r="3" fill="#3E63DD"/><circle cx="16" cy="8" r="3" fill="#2FA36B"/><circle cx="12" cy="14" r="3" fill="#E8912D"/><rect x="3" y="16" width="10" height="6" rx="2" fill="#3E63DD"/><rect x="13" y="16" width="8" height="6" rx="2" fill="#2FA36B"/></svg>',
  },
  {
    key: 'semi', title: '半结构化面试',
    desc: '在结构化基础上加 1-2 道追问，AI 根据你的回答灵活调整方向，更接近真实面试。',
    qRange: '4-7', tRange: '22-28 min',
    icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="10" rx="2" fill="#3E63DD"/><rect x="6" y="9" width="12" height="2" rx="1" fill="#fff"/><rect x="6" y="13" width="8" height="2" rx="1" fill="#fff"/><rect x="9" y="18" width="6" height="3" rx="1.5" fill="#7C6BD6"/></svg>',
  },
]

function select(key) {
  flow.setForm(key, {
    enableFollowup: key === 'semi',
    peerCount: key === 'group' ? 5 : 0,
  })
}

function practicedCount(key) {
  const s = stats.value.find(x => x.form_type === key)
  return s ? s.practiced_count : 0
}

function saveFavorite() {
  localStorage.setItem('mockwise_favorite_form', flow.formType)
  message.success('已保存为常用面试形式')
}

function next() {
  router.push('/set')
}

onMounted(async () => {
  try {
    stats.value = await dashboardApi.formStats()
  } catch (e) { /* 静默 */ }
})
</script>

<style scoped>
.form-grid { display: grid; gap: 20px; grid-template-columns: repeat(3, 1fr); }
.opt-card {
  background: var(--card); border: 2px solid var(--border);
  border-radius: var(--r-card); padding: 24px;
  display: flex; flex-direction: column; gap: 12px;
  cursor: pointer; transition: all .2s;
}
.opt-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: var(--shadow-md); }
.opt-card.active { border-color: var(--primary); background: var(--primary-soft); }
.opt-card .ico {
  width: 44px; height: 44px; border-radius: 12px; background: var(--primary-soft);
  display: flex; align-items: center; justify-content: center; color: var(--primary);
}
.opt-card.active .ico { background: #fff; }
.opt-card h4 { margin: 0; font-size: 16px; }
.opt-card p { margin: 0; color: var(--text-2); font-size: 13px; }
.opt-card .meta {
  display: flex; gap: 14px; padding-top: 12px; margin-top: 8px;
  border-top: 1px dashed var(--border); font-size: 12px; color: var(--text-3);
}
.opt-card .meta b { color: var(--text-1); font-weight: 700; }

.action-bar {
  position: sticky; bottom: 0;
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 24px; margin-top: 28px;
  background: var(--card); border: 1px solid var(--border); border-radius: var(--r-card);
  box-shadow: var(--shadow-md);
}

@media (max-width: 900px) { .form-grid { grid-template-columns: 1fr; } }
</style>
