<template>
  <div>
    <h2 class="section-title">我的简历</h2>
    <p class="section-sub">上传简历（PDF / Word / TXT）或直接粘贴文本，AI 会解析你的经历并生成画像。<b>半结构化面试将基于你的简历个性化提问。</b></p>

    <div class="resume-layout">
      <!-- 左：上传 / 粘贴 -->
      <div class="mw-card upload-card">
        <a-tabs v-model:activeKey="tab">
          <a-tab-pane key="upload" tab="上传文件">
            <a-upload-dragger
              :before-upload="handleUpload"
              :show-upload-list="false"
              accept=".pdf,.docx,.doc,.txt,.md"
              :disabled="analyzing"
            >
              <p class="ant-upload-drag-icon">
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none">
                  <path d="M12 16V4m0 0L8 8m4-4l4 4" stroke="#3E63DD" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="#3E63DD" stroke-width="1.8" stroke-linecap="round"/>
                </svg>
              </p>
              <p class="ant-upload-text">点击或拖拽简历到此处</p>
              <p class="ant-upload-hint">支持 PDF / Word(.docx) / TXT，单个文件不超过 10MB</p>
            </a-upload-dragger>
          </a-tab-pane>
          <a-tab-pane key="paste" tab="粘贴文本">
            <a-textarea
              v-model:value="pastedText"
              placeholder="将简历内容粘贴到这里，建议包含：教育背景、工作/实习经历、项目经验、技能证书…"
              :rows="10"
              :disabled="analyzing"
            />
            <a-button type="primary" block style="margin-top:12px;" :loading="analyzing" @click="submitPaste">
              分析简历
            </a-button>
          </a-tab-pane>
        </a-tabs>

        <a-alert
          v-if="analyzeMsg" :message="analyzeMsg" type="info" show-icon
          style="margin-top:12px;"
        />
      </div>

      <!-- 右：画像 -->
      <div class="mw-card profile-card">
        <div class="profile-head">
          <h3 style="margin:0;">AI 简历画像</h3>
          <a-tag v-if="profile" :color="profile.engine === 'deepseek' ? 'blue' : 'default'">
            {{ profile.engine === 'deepseek' ? 'DeepSeek 分析' : '规则分析' }}
          </a-tag>
        </div>

        <a-spin :spinning="analyzing">
          <template v-if="profile && profile.summary">
            <div class="prof-name">
              {{ profile.candidate_name || '候选人' }}
              <span v-if="profile.target_position" class="prof-pos">· {{ profile.target_position }}</span>
              <span v-if="profile.years_exp" class="prof-exp">{{ profile.years_exp }} 年经验</span>
            </div>
            <p class="prof-summary">{{ profile.summary }}</p>

            <div v-if="profile.skills?.length" class="prof-block">
              <div class="block-title">核心技能</div>
              <div class="tag-row">
                <a-tag v-for="s in profile.skills" :key="s" color="blue">{{ s }}</a-tag>
              </div>
            </div>

            <div v-if="profile.projects?.length" class="prof-block">
              <div class="block-title">代表经历</div>
              <ul class="dot-list"><li v-for="(p, i) in profile.projects" :key="i">{{ p }}</li></ul>
            </div>

            <div v-if="profile.highlights?.length" class="prof-block">
              <div class="block-title">简历亮点</div>
              <ul class="dot-list good"><li v-for="(h, i) in profile.highlights" :key="i">{{ h }}</li></ul>
            </div>

            <div v-if="profile.weaknesses?.length" class="prof-block">
              <div class="block-title">可能被追问 / 薄弱点</div>
              <ul class="dot-list warn"><li v-for="(w, i) in profile.weaknesses" :key="i">{{ w }}</li></ul>
            </div>

            <div v-if="profile.suggested_questions?.length" class="prof-block">
              <div class="block-title">面试中可能被问到</div>
              <ul class="q-list">
                <li v-for="(q, i) in profile.suggested_questions" :key="i">
                  <span class="q-idx">{{ i + 1 }}</span>{{ q }}
                </li>
              </ul>
            </div>

            <a-alert
              type="success" show-icon style="margin-top:12px;"
              message="简历已激活：开始「半结构化面试」时，AI 将基于以上内容为你个性化出题。"
            />
          </template>
          <a-empty v-else description="上传简历后，这里会展示 AI 分析的画像" style="padding:40px 0;" />
        </a-spin>
      </div>
    </div>

    <!-- 历史简历 -->
    <div class="mw-card" style="margin-top:18px;" v-if="history.length">
      <h4 style="margin:0 0 12px;">历史简历</h4>
      <div class="hist-row" v-for="r in history" :key="r.id" :class="{ active: r.is_active }">
        <div class="hist-name">
          📄 {{ r.filename }}
          <a-tag v-if="r.is_active" color="green">使用中</a-tag>
        </div>
        <div class="hist-meta">
          <a-tag :color="r.engine === 'deepseek' ? 'blue' : 'default'">{{ r.engine === 'deepseek' ? 'AI' : '规则' }}</a-tag>
          <span>{{ r.created_at }}</span>
        </div>
        <div class="hist-ops">
          <a-button size="small" v-if="!r.is_active" @click="activate(r.id)">设为当前</a-button>
          <a-button size="small" danger @click="remove(r.id)">删除</a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { resumeApi } from '@/api'

const tab = ref('upload')
const pastedText = ref('')
const analyzing = ref(false)
const analyzeMsg = ref('')
const profile = ref(null)
const history = ref([])

async function handleUpload(file) {
  analyzing.value = true
  analyzeMsg.value = '正在上传并解析简历，AI 分析约需 10-30 秒…'
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await resumeApi.upload(fd)
    profile.value = res.profile
    message.success('简历分析完成')
    loadHistory()
  } catch (e) {
    message.error(e.message || '简历解析失败，请改用粘贴文本')
  } finally {
    analyzing.value = false
    analyzeMsg.value = ''
  }
  return false // 阻止 antd 自动上传
}

async function submitPaste() {
  if (!pastedText.value.trim() || pastedText.value.trim().length < 20) {
    message.warning('请粘贴至少 20 字的简历内容')
    return
  }
  analyzing.value = true
  analyzeMsg.value = 'AI 正在分析简历内容…'
  try {
    const fd = new FormData()
    fd.append('text', pastedText.value)
    const res = await resumeApi.upload(fd)
    profile.value = res.profile
    pastedText.value = ''
    message.success('简历分析完成')
    loadHistory()
  } catch (e) {
    message.error('分析失败，请重试')
  } finally {
    analyzing.value = false
    analyzeMsg.value = ''
  }
}

async function loadHistory() {
  try {
    const [list, active] = await Promise.all([resumeApi.list(), resumeApi.active()])
    history.value = list || []
    if (active) profile.value = active.profile
  } catch (e) { /* */ }
}

async function activate(id) {
  await resumeApi.activate(id)
  message.success('已设为当前简历')
  loadHistory()
}

async function remove(id) {
  await resumeApi.remove(id)
  message.success('已删除')
  loadHistory()
}

onMounted(loadHistory)
</script>

<style scoped>
.resume-layout { display: grid; grid-template-columns: 1fr 1.2fr; gap: 18px; }
.upload-card { padding: 20px; }
.profile-card { padding: 20px; min-height: 420px; }
.profile-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.prof-name { font-size: 17px; font-weight: 700; }
.prof-pos { font-size: 14px; color: var(--primary); margin-left: 6px; font-weight: 600; }
.prof-exp { font-size: 12px; color: var(--text-3); margin-left: 8px; }
.prof-summary { font-size: 13px; line-height: 1.7; color: var(--text-2); background: var(--bg); padding: 12px; border-radius: 10px; }
.prof-block { margin-top: 14px; }
.block-title { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
.tag-row { display: flex; flex-wrap: wrap; gap: 4px; }
.dot-list { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; color: var(--text-2); }
.dot-list.good li { color: var(--success); }
.dot-list.warn li { color: var(--warning); }
.q-list { margin: 0; padding: 0; list-style: none; }
.q-list li {
  font-size: 13px; line-height: 1.7; padding: 8px 10px 8px 34px;
  background: var(--bg); border-radius: 8px; margin-bottom: 6px; position: relative;
}
.q-idx {
  position: absolute; left: 10px; top: 8px; width: 18px; height: 18px;
  background: var(--primary); color: #fff; border-radius: 50%;
  font-size: 11px; display: inline-flex; align-items: center; justify-content: center; font-weight: 700;
}
.hist-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: var(--bg); border-radius: 10px; margin-bottom: 8px;
  border: 1.5px solid transparent;
}
.hist-row.active { border-color: var(--success); }
.hist-name { font-size: 13px; font-weight: 600; }
.hist-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-3); }
.hist-ops { display: flex; gap: 8px; }
@media (max-width: 900px) { .resume-layout { grid-template-columns: 1fr; } }
</style>
