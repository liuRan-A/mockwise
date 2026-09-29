<template>
  <div>
    <h2 class="section-title">管理后台</h2>
    <p class="section-sub">平台运营总览、用户管理、面试场次与简历分析数据。</p>

    <!-- 统计卡片 -->
    <div class="stat-grid" v-if="stats">
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.total_users }}</div>
        <div class="s-label">注册用户 <span class="s-sub">今日 +{{ stats.new_users_today }}</span></div>
      </div>
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.total_sessions }}</div>
        <div class="s-label">面试场次 <span class="s-sub">完成 {{ stats.done_sessions }}</span></div>
      </div>
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.avg_score }}</div>
        <div class="s-label">全站平均分 <span class="s-sub">近7天 {{ stats.week_practices }} 场</span></div>
      </div>
      <div class="mw-card stat-card">
        <div class="s-num">{{ stats.total_resumes }}</div>
        <div class="s-label">上传简历</div>
      </div>
    </div>

    <!-- 趋势 + 形式分布 -->
    <div class="chart-row">
      <div class="mw-card chart-card">
        <div class="card-title">近 7 天练习趋势</div>
        <div class="trend-bars">
          <div v-for="t in stats?.trend" :key="t.date" class="t-col">
            <div class="t-bar" :style="{ height: barH(t.count) + 'px' }"></div>
            <div class="t-val">{{ t.count }}</div>
            <div class="t-date">{{ t.date }}</div>
          </div>
        </div>
      </div>
      <div class="mw-card chart-card">
        <div class="card-title">面试形式分布</div>
        <div class="dist-list">
          <div v-for="d in stats?.form_distribution" :key="d.name" class="dist-row">
            <span class="d-name">{{ d.name }}</span>
            <div class="d-bar-shell"><span :style="{ width: distPct(d.value) + '%' }"></span></div>
            <span class="d-val">{{ d.value }}</span>
          </div>
          <a-empty v-if="!stats?.form_distribution?.length" description="暂无数据" />
        </div>
      </div>
    </div>

    <!-- 数据 Tabs -->
    <div class="mw-card" style="margin-top:18px;">
      <a-tabs v-model:activeKey="tab">
        <a-tab-pane key="users" :tab="`用户（${users.total}）`">
          <div class="toolbar">
            <a-input-search v-model:value="userKw" placeholder="搜索昵称/手机号" style="max-width:280px;" @search="loadUsers" />
          </div>
          <a-table :data-source="users.list" :columns="userCols" row-key="id" :pagination="false" size="middle">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'role'">
                <a-tag :color="record.role === 'admin' ? 'red' : 'default'">{{ record.role === 'admin' ? '管理员' : '用户' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'avg_score'">
                <span :style="{ color: record.avg_score >= 80 ? '#2FA36B' : record.avg_score >= 70 ? '' : '#E8912D' }">
                  {{ record.avg_score || '—' }}
                </span>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'active' ? 'green' : 'orange'">{{ record.status === 'active' ? '正常' : '已禁用' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'op'">
                <a-button size="small" :type="record.status === 'active' ? 'default' : 'primary'"
                  @click="toggleUser(record)">
                  {{ record.status === 'active' ? '禁用' : '启用' }}
                </a-button>
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="users.page <= 1" @click="users.page--; loadUsers()">上一页</a-button>
            <span>第 {{ users.page }} 页</span>
            <a-button size="small" :disabled="users.page * users.page_size >= users.total" @click="users.page++; loadUsers()">下一页</a-button>
          </div>
        </a-tab-pane>

        <a-tab-pane key="records" :tab="`面试回放（${records.total}）`">
          <!-- 顶部工具栏：按形式筛选 + 关键词搜索 -->
          <div class="toolbar records-toolbar">
            <a-segmented
              v-model:value="recordFormType"
              :options="formOptions"
              @change="reloadRecords"
            />
            <a-input-search
              v-model:value="recordKw"
              placeholder="按用户/手机号/套题搜索"
              style="max-width:280px;"
              @search="reloadRecords"
              allow-clear
            />
            <a-button @click="reloadRecords">刷新</a-button>
          </div>

          <div class="record-stats" v-if="records.list.length">
            <div class="rs-item"><span class="rs-num">{{ records.total }}</span><span class="rs-label">总场次</span></div>
            <div class="rs-item"><span class="rs-num">{{ answeredCount }}</span><span class="rs-label">已作答</span></div>
            <div class="rs-item"><span class="rs-num">{{ audioCount }}</span><span class="rs-label">含录音</span></div>
            <div class="rs-item"><span class="rs-num">{{ videoCount }}</span><span class="rs-label">含录像</span></div>
          </div>

          <a-table :data-source="records.list" :columns="recordCols" row-key="id" :pagination="false" size="middle">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'form_type'">
                <a-tag :color="{ structured: 'blue', group: 'purple', semi: 'cyan' }[record.form_type]">
                  {{ record.form_label }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'total_score'">
                {{ record.total_score ? record.total_score.toFixed(1) : '—' }}
              </template>
              <template v-else-if="column.key === 'duration'">
                {{ fmtMs(record.duration_ms) }}
              </template>
              <template v-else-if="column.key === 'saves'">
                <a-tag color="green" v-if="record.answered_count">转写 ✓</a-tag>
                <a-tag :color="record.has_audio ? 'cyan' : 'default'">录音 {{ record.has_audio ? '✓' : '—' }}</a-tag>
                <a-tag :color="record.has_video ? 'purple' : 'default'">录像 {{ record.has_video ? '✓' : '—' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'op'">
                <a-button size="small" type="primary" :disabled="!record.answered_count" @click="openReplay(record)">
                  打开回放
                </a-button>
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="records.page <= 1" @click="records.page--; reloadRecords()">上一页</a-button>
            <span>第 {{ records.page }} 页</span>
            <a-button size="small" :disabled="records.page * records.page_size >= records.total" @click="records.page++; reloadRecords()">下一页</a-button>
          </div>
        </a-tab-pane>

        <a-tab-pane key="sessions" :tab="`面试场次（${sessions.total}）`">
          <a-table :data-source="sessions.list" :columns="sessionCols" row-key="id" :pagination="false" size="middle">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'form_type'">
                <a-tag :color="{ structured: 'blue', group: 'purple', semi: 'cyan' }[record.form_type]">
                  {{ record.form_label }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'done' ? 'green' : 'default'">{{ statusLabel(record.status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'total_score'">
                {{ record.total_score ? record.total_score.toFixed(1) : '—' }}
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="sessions.page <= 1" @click="sessions.page--; loadSessions()">上一页</a-button>
            <span>第 {{ sessions.page }} 页</span>
            <a-button size="small" :disabled="sessions.page * sessions.page_size >= sessions.total" @click="sessions.page++; loadSessions()">下一页</a-button>
          </div>
        </a-tab-pane>

        <a-tab-pane key="resumes" :tab="`简历分析（${resumes.total}）`">
          <a-table :data-source="resumes.list" :columns="resumeCols" row-key="id" :pagination="false" size="middle">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'engine'">
                <a-tag :color="record.engine === 'deepseek' ? 'blue' : 'default'">{{ record.engine === 'deepseek' ? 'AI' : '规则' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'skills'">
                <a-tag v-for="s in (record.skills || []).slice(0, 3)" :key="s" style="margin-bottom:2px;">{{ s }}</a-tag>
              </template>
            </template>
          </a-table>
          <div class="pager">
            <a-button size="small" :disabled="resumes.page <= 1" @click="resumes.page--; loadResumes()">上一页</a-button>
            <span>第 {{ resumes.page }} 页</span>
            <a-button size="small" :disabled="resumes.page * resumes.page_size >= resumes.total" @click="resumes.page++; loadResumes()">下一页</a-button>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 面试回放弹窗 -->
    <ReplayModal v-model:open="replayOpen" :sessionId="replaySessionId" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { adminApi } from '@/api'
import ReplayModal from '@/components/ReplayModal.vue'

const router = useRouter()
const stats = ref(null)
const tab = ref('users')

const users = ref({ list: [], total: 0, page: 1, page_size: 10 })
const sessions = ref({ list: [], total: 0, page: 1, page_size: 10 })
const resumes = ref({ list: [], total: 0, page: 1, page_size: 10 })
const records = ref({ list: [], total: 0, page: 1, page_size: 10 })
const userKw = ref('')
const recordKw = ref('')
const recordFormType = ref('')
const formOptions = [
  { label: '全部', value: '' },
  { label: '结构化', value: 'structured' },
  { label: '群面', value: 'group' },
  { label: '半结构化', value: 'semi' },
]

// 面试回放弹窗
const replayOpen = ref(false)
const replaySessionId = ref(null)
const answeredCount = computed(() => records.value.list.filter(r => r.answered_count).length)
const audioCount = computed(() => records.value.list.filter(r => r.has_audio).length)
const videoCount = computed(() => records.value.list.filter(r => r.has_video).length)

const userCols = [
  { title: '昵称', dataIndex: 'nickname', key: 'nickname' },
  { title: '手机号', dataIndex: 'phone', key: 'phone' },
  { title: '目标岗位', dataIndex: 'target_position', key: 'target_position', customRender: ({ text }) => text || '—' },
  { title: '角色', key: 'role' },
  { title: '练习次数', dataIndex: 'practice_count', key: 'practice_count' },
  { title: '平均分', key: 'avg_score' },
  { title: '简历', dataIndex: 'resume_count', key: 'resume_count' },
  { title: '状态', key: 'status' },
  { title: '操作', key: 'op' },
]
const sessionCols = [
  { title: '场次ID', dataIndex: 'id', key: 'id' },
  { title: '用户', dataIndex: 'user_name', key: 'user_name' },
  { title: '形式', key: 'form_type' },
  { title: '套题', dataIndex: 'set_name', key: 'set_name' },
  { title: '总分', key: 'total_score' },
  { title: '状态', key: 'status' },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at' },
]
const recordCols = [
  { title: '场次', dataIndex: 'id', key: 'id', width: 80 },
  { title: '用户', dataIndex: 'user_name', key: 'user_name' },
  { title: '形式', key: 'form_type' },
  { title: '套题', dataIndex: 'set_name', key: 'set_name' },
  { title: '题数', key: 'qcount', customRender: ({ record }) => `${record.answered_count}/${record.question_count}` },
  { title: '时长', key: 'duration' },
  { title: '总分', key: 'total_score' },
  { title: '保存情况', key: 'saves' },
  { title: '开始时间', dataIndex: 'started_at', key: 'started_at' },
  { title: '操作', key: 'op', width: 110 },
]
const resumeCols = [
  { title: 'ID', dataIndex: 'id', key: 'id' },
  { title: '用户', dataIndex: 'user_name', key: 'user_name' },
  { title: '文件', dataIndex: 'filename', key: 'filename' },
  { title: '候选人', dataIndex: 'candidate_name', key: 'candidate_name', customRender: ({ text }) => text || '—' },
  { title: '目标岗位', dataIndex: 'target_position', key: 'target_position', customRender: ({ text }) => text || '—' },
  { title: '技能', key: 'skills' },
  { title: '引擎', key: 'engine' },
  { title: '上传时间', dataIndex: 'created_at', key: 'created_at' },
]

function barH(c) {
  const max = Math.max(...(stats.value?.trend || []).map(t => t.count), 1)
  return 8 + (c / max) * 90
}
function distPct(v) {
  const max = Math.max(...(stats.value?.form_distribution || []).map(d => d.value), 1)
  return Math.round(v / max * 100)
}
function statusLabel(s) {
  return { done: '已完成', running: '进行中', idle: '待开始', aborted: '已中断', paused: '已暂停' }[s] || s
}
function fmtMs(ms) {
  ms = ms || 0
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}

async function loadStats() {
  try { stats.value = await adminApi.stats() } catch (e) {
    message.error('无管理员权限或加载失败')
    router.push('/dashboard')
  }
}
async function loadUsers() {
  const r = await adminApi.users({ keyword: userKw.value, page: users.value.page, page_size: 10 })
  users.value.list = r.list; users.value.total = r.total
}
async function loadSessions() {
  const r = await adminApi.sessions({ page: sessions.value.page, page_size: 10 })
  sessions.value.list = r.list; sessions.value.total = r.total
}
async function loadResumes() {
  const r = await adminApi.resumes({ page: resumes.value.page, page_size: 10 })
  resumes.value.list = r.list; resumes.value.total = r.total
}
async function reloadRecords() {
  const r = await adminApi.records({
    keyword: recordKw.value,
    form_type: recordFormType.value,
    page: records.value.page,
    page_size: 10,
  }).catch(() => ({ list: [], total: 0 }))
  records.value.list = r.list || []
  records.value.total = r.total || 0
}
async function toggleUser(record) {
  const next = record.status === 'active' ? 'paused' : 'active'
  await adminApi.setUserStatus(record.id, next)
  message.success(next === 'active' ? '已启用' : '已禁用')
  loadUsers()
}
function openReplay(record) {
  replaySessionId.value = record.id
  replayOpen.value = true
}

onMounted(() => {
  loadStats()
  loadUsers()
  loadSessions()
  loadResumes()
  reloadRecords()
})
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.stat-card { padding: 20px; }
.s-num { font-size: 32px; font-weight: 800; color: var(--primary); }
.s-label { font-size: 13px; color: var(--text-2); margin-top: 4px; }
.s-sub { font-size: 12px; color: var(--text-3); margin-left: 6px; }
.chart-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }
.chart-card { padding: 20px; }
.card-title { font-size: 14px; font-weight: 700; margin-bottom: 16px; }
.trend-bars { display: flex; align-items: flex-end; gap: 14px; height: 140px; }
.t-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
.t-bar { width: 60%; background: linear-gradient(180deg, #3E63DD, #7C6BD6); border-radius: 6px 6px 0 0; min-height: 8px; }
.t-val { font-size: 12px; font-weight: 700; margin-top: 4px; }
.t-date { font-size: 11px; color: var(--text-3); }
.dist-list { display: flex; flex-direction: column; gap: 14px; }
.dist-row { display: flex; align-items: center; gap: 10px; }
.d-name { font-size: 13px; width: 70px; }
.d-bar-shell { flex: 1; height: 10px; background: var(--border-soft); border-radius: 5px; overflow: hidden; }
.d-bar-shell > span { display: block; height: 100%; background: var(--success); border-radius: 5px; }
.d-val { font-size: 13px; font-weight: 700; width: 36px; text-align: right; }
.toolbar { margin-bottom: 12px; display: flex; gap: 10px; align-items: center; }
.records-toolbar { flex-wrap: wrap; }

.record-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
  margin-bottom: 14px;
}
.rs-item {
  padding: 14px; background: var(--bg); border-radius: 10px;
  display: flex; flex-direction: column; gap: 4px;
}
.rs-num { font-size: 22px; font-weight: 800; color: var(--primary); }
.rs-label { font-size: 12px; color: var(--text-3); }

.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 14px; font-size: 13px; color: var(--text-3); }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } .chart-row { grid-template-columns: 1fr; } .record-stats { grid-template-columns: repeat(2, 1fr); } }
</style>
