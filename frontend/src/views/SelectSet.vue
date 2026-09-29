<template>
  <div class="container">
    <StepsIndicator :current="2" />

    <h2 class="section-title">选择套题</h2>
    <p class="section-sub">已为你按岗位匹配 {{ sets.length }} 套适合「{{ targetPosition }}」的题目，点击任意卡片即可选中。</p>

    <a-spin :spinning="loading">
      <div class="form-grid">
        <div
          v-for="s in sets"
          :key="s.id"
          class="opt-card"
          :class="{ active: selectedId === s.id }"
          @click="select(s)"
        >
          <div class="paper-tag-row">
            <span class="mw-tag blue">{{ s.position_type || s.industry || '通用' }}</span>
            <span class="mw-tag orange">{{ diffLabel(s.difficulty) }}</span>
            <span class="mw-tag green">适配度 {{ Math.round(s.match_score) }}%</span>
          </div>
          <h4>{{ s.name }}</h4>
          <p>{{ s.description }}</p>
          <div class="meta" style="border-top: 1px dashed var(--border); padding-top: 12px;">
            <span>题数 <b>{{ s.question_count }}</b></span>
            <span>预计 <b>{{ s.est_minutes }} min</b></span>
          </div>
        </div>
      </div>
    </a-spin>

    <div class="action-bar">
      <a-button size="large" @click="$router.push('/form')">← 上一步</a-button>
      <div style="display:flex; gap:12px;">
        <a-button size="large" @click="randomPick" :disabled="!sets.length">随机抽 4 题</a-button>
        <a-button type="primary" size="large" :disabled="!selectedId" @click="start">开始作答 →</a-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import StepsIndicator from '@/components/StepsIndicator.vue'
import { useFlowStore } from '@/store/flow'
import { useUserStore } from '@/store/user'
import { questionSetApi } from '@/api'

const router = useRouter()
const flow = useFlowStore()
const userStore = useUserStore()

const sets = ref([])
const selectedId = ref(null)
const loading = ref(false)

const targetPosition = computed(() => userStore.user?.target_position || 'AI 方案架构师')

function diffLabel(d) {
  return { easy: '简单', medium: '中等', hard: '进阶' }[d] || d
}

function select(s) {
  selectedId.value = s.id
  flow.setSet(s)
}

async function randomPick() {
  if (!sets.value.length) return
  const s = sets.value[Math.floor(Math.random() * sets.value.length)]
  select(s)
  message.success(`已为你随机选中「${s.name}」`)
}

async function start() {
  if (!selectedId.value) return
  try {
    const detail = await questionSetApi.detail(selectedId.value)
    flow.setSet(detail)
    router.push('/answer')
  } catch (e) { /* */ }
}

onMounted(async () => {
  loading.value = true
  try {
    // 按所选面试形式过滤题库：三种形式各自独立题库，互不混用；专项练习题集仅在专项页展示
    sets.value = ((await questionSetApi.list()) || []).filter(s =>
      s.industry !== '专项练习' && (s.form_type || 'structured') === flow.formType
    )
    // 如果 flow 里已选，回显
    if (flow.selectedSet) selectedId.value = flow.selectedSet.id
    else if (sets.value.length) {
      selectedId.value = sets.value[0].id
      flow.setSet(sets.value[0])
    }
  } catch (e) {
    sets.value = []
  } finally {
    loading.value = false
  }
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
.paper-tag-row { display: flex; gap: 6px; flex-wrap: wrap; }
.opt-card h4 { margin: 0; font-size: 16px; }
.opt-card p { margin: 0; color: var(--text-2); font-size: 13px; }
.opt-card .meta { display: flex; gap: 14px; font-size: 12px; color: var(--text-3); }
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
