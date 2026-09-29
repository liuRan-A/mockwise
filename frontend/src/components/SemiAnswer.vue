<template>
  <a-spin :spinning="loading">
    <div class="semi-layout">
      <!-- 左：面试官信息 + 进度 -->
      <aside class="mw-card side-card">
        <span class="mw-tag orange" style="align-self:flex-start;">半结构化面试 · {{ currentQuestion?.category || '深挖' }}</span>
        <div class="interviewer">
          <div class="avatar" style="background:var(--info);">陈</div>
          <div>
            <div class="i-name">陈顾问 · AI</div>
            <div class="i-bio">资深面试官 · 擅长项目深挖与追问验证</div>
          </div>
        </div>
        <div class="progress-block">
          <div class="p-row"><span>题目进度</span><span>{{ qIndex + 1 }} / {{ questions.length }}</span></div>
          <div class="bar-shell"><span :style="{ width: ((qIndex + 1) / Math.max(questions.length, 1) * 100) + '%' }"></span></div>
          <div class="p-row" style="margin-top:8px;"><span>本题追问</span><span>{{ followupCount }} / {{ MAX_FOLLOWUP }}</span></div>
          <div class="bar-shell"><span :style="{ width: (followupCount / MAX_FOLLOWUP * 100) + '%', background: 'var(--warning)' }"></span></div>
        </div>
        <div class="q-tip">
          半结构化特点：AI 会针对你回答中的细节层层追问，请确保经历真实、可展开。追问最多 {{ MAX_FOLLOWUP }} 轮。
        </div>
      </aside>

      <!-- 中：对话流 -->
      <section class="mw-card chat-card">
        <div class="chat-head">
          <h3 style="margin:0;font-size:15px;">面试对话</h3>
          <div style="display:flex;gap:8px;align-items:center;">
            <span v-if="asrMode === 'ifly'" class="mw-chip">讯飞实时转写</span>
            <span class="mw-chip" :class="{ warning: recording }">{{ recording ? '● ' + fmt(recSecs) : '未在录音' }}</span>
          </div>
        </div>

        <div class="chat-stream" ref="streamRef">
          <div v-for="(m, i) in chat" :key="i" class="msg-row" :class="m.who">
            <div v-if="m.who === 'ai'" class="msg-avatar" style="background:var(--info);">陈</div>
            <div class="msg-body">
              <div class="msg-meta">{{ m.who === 'ai' ? '陈顾问 · 面试官' : '你 · ' + m.ts }}</div>
              <div class="msg-bubble" :class="m.who" :style="m.kind === 'followup' ? { borderLeft: '3px solid var(--warning)' } : {}">
                <span v-if="m.kind === 'followup'" class="followup-tag">追问 {{ m.seq }}</span>
                {{ m.text }}
              </div>
              <!-- AI 反馈卡片 -->
              <div v-if="m.feedback" class="fb-card">
                <div class="fb-head"><span class="ai-badge">AI</span> AI 对你回答的理解</div>
                <div class="fb-understanding">{{ m.feedback.understanding }}</div>
                <ul v-if="m.feedback.highlights?.length" class="fb-list good">
                  <li v-for="(h, j) in m.feedback.highlights" :key="j">{{ h }}</li>
                </ul>
                <ul v-if="m.feedback.suggestions?.length" class="fb-list">
                  <li v-for="(s, j) in m.feedback.suggestions" :key="j">{{ s }}</li>
                </ul>
              </div>
            </div>
          </div>
          <div v-if="aiTyping" class="msg-row ai">
            <div class="msg-avatar" style="background:var(--info);">陈</div>
            <div class="msg-body">
              <div class="msg-meta">陈顾问正在输入</div>
              <div class="msg-bubble ai typing"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="chat-input">
          <div class="input-btns">
            <a-input-search
              v-if="textMode"
              v-model:value="textInput"
              placeholder="输入你的回答，回车发送"
              enter-button="发送"
              style="flex:1; min-width:240px;"
              @search="sendText"
            />
            <a-button @click="toggleTextMode">{{ textMode ? '切到语音' : '切到文字' }}</a-button>
            <button class="mic-btn" :class="{ recording }" :disabled="aiTyping || submitting" @click="toggleRecord">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="5" y="2" width="4" height="7" rx="2" fill="#fff"/>
                <rect x="3" y="7" width="8" height="1.5" rx="0.75" fill="#fff"/>
              </svg>
              {{ recording ? '结束回答' : (awaitingAnswer ? '开始回答' : '回答追问') }}
            </button>
            <a-button
              v-if="stage === 'main' && !recording"
              @click="skipFollowup"
            >跳过追问，进入下一题 →</a-button>
            <a-button
              v-else-if="stage === 'followup' && !recording && followupCount >= 1"
              @click="nextQuestion"
            >{{ qIndex < questions.length - 1 ? '下一题 →' : '提交，生成报告 →' }}</a-button>
          </div>
          <span class="action-hint">{{ inputHint }}</span>
        </div>
      </section>

      <!-- 右：实时指标 -->
      <aside class="mw-card metric-card">
        <h4 style="margin:0;font-size:14px;">实时表现指标</h4>
        <div class="metric-row"><span class="n">语速</span><span class="v">{{ metrics.wpm }} 字/min</span></div>
        <div class="metric-row"><span class="n">停顿次数</span><span class="v">{{ metrics.pause_count }} 次</span></div>
        <div class="metric-row">
          <span class="n">口头禅</span>
          <span class="v" :style="{ color: metrics.filler_count > 2 ? 'var(--warning)' : '' }">
            {{ metrics.filler_count }} 次{{ metrics.filler_count > 2 ? ' 偏高' : '' }}
          </span>
        </div>
        <div class="metric-row"><span class="n">回答完整度</span><span class="v">{{ metrics.completeness }}%</span></div>
        <div class="bar-shell"><span :style="{ width: metrics.completeness + '%' }"></span></div>
        <div class="q-tip" v-if="currentQuestion?.dimension">
          本题维度「{{ currentQuestion.dimension }}」，追问通常验证经历真实性，准备好数据与细节。
        </div>
      </aside>
    </div>
  </a-spin>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useFlowStore } from '@/store/flow'
import { sessionApi } from '@/api'
import { createAsrClient } from '@/utils/asr'

const props = defineProps({
  session: { type: Object, default: null },
  sessionId: { type: Number, default: null },
  questions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const router = useRouter()
const flow = useFlowStore()

const MAX_FOLLOWUP = 2
const qIndex = ref(0)
const stage = ref('main')            // main / followup
const followupCount = ref(0)
const chat = ref([])
const aiTyping = ref(false)
const awaitingAnswer = ref(false)    // 是否有未回答的问题（主问题或追问）
const submitting = ref(false)

const recording = ref(false)
const textMode = ref(false)
const textInput = ref('')
const recSecs = ref(0)
const asrMode = ref('')
let asrClient = null
let committedText = ''          // 已通过讯飞 final 确认、跨会话累计的文本
let liveText = ''               // 界面实时显示文本，作为未拿到 final 时的兜底
let recTimer = null
const streamRef = ref(null)

// 每题收集：主回答 + 追问回答
const mainAnswer = ref('')
const followupAnswers = ref([])

const metrics = reactive({ wpm: 0, pause_count: 0, filler_count: 0, completeness: 0 })

const currentQuestion = computed(() => {
  const sq = props.questions?.[qIndex.value]
  if (!sq) return null
  const setQ = flow.selectedSet?.questions?.find(q => q.id === sq.question_id)
  const base = setQ ? { ...setQ, ...sq } : { ...sq }
  base.content = base.content || sq.question_content || ''
  base.dimension = base.dimension || sq.question_dimension || ''
  base.category = base.category || sq.question_category || ''
  return base
})

const inputHint = computed(() => {
  if (aiTyping.value) return '面试官正在输入…'
  if (stage.value === 'main') return '请回答主问题，建议用 STAR 法则展开（1.5～2 分钟）'
  return '请针对面试官的追问补充细节，回答后可进入下一题'
})

function fmt(s) {
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}

function scrollBottom() {
  nextTick(() => { if (streamRef.value) streamRef.value.scrollTop = streamRef.value.scrollHeight })
}

function pushChat(m) { chat.value.push(m); scrollBottom() }

async function aiSay(text, kind = 'main') {
  aiTyping.value = true
  scrollBottom()
  await new Promise(r => setTimeout(r, 500 + Math.random() * 400))
  aiTyping.value = false
  pushChat({ who: 'ai', text, kind, seq: kind === 'followup' ? followupCount.value : 0 })
  awaitingAnswer.value = true
}

// —— 开始一道题 ——
async function startQuestion() {
  stage.value = 'main'
  followupCount.value = 0
  mainAnswer.value = ''
  followupAnswers.value = []
  resetMetrics()
  if (currentQuestion.value?.content) {
    await aiSay(currentQuestion.value.content, 'main')
  }
}

function resetMetrics() {
  Object.assign(metrics, { wpm: 0, pause_count: 0, filler_count: 0, completeness: 0 })
}

function updateMetrics(text, secs) {
  const chars = (text || '').length
  const mins = Math.max(secs, 1) / 60
  metrics.wpm = Math.round(chars / mins)
  metrics.filler_count = (text || '').match(/嗯|啊|呃|那个|就是/g || []).length
  metrics.pause_count = Math.max(0, ((text || '').match(/。|！|？/g) || []).length - 1)
  metrics.completeness = Math.min(96, Math.round(chars / 4))
}

// —— 用户回答完毕 → 请求反馈 + 可能追问 ——
async function onMyAnswer(text, secs) {
  if (stage.value === 'main') mainAnswer.value = text
  else followupAnswers.value.push(text)
  updateMetrics(text, secs)
  awaitingAnswer.value = false

  const sq = props.questions?.[qIndex.value]
  if (!sq) return
  aiTyping.value = true
  scrollBottom()
  try {
    // 追问轮次带上完整上下文（主回答 + 历轮追问），保证 AI 理解连贯
    const contextText = [mainAnswer.value, ...followupAnswers.value]
      .filter(Boolean).join('\n')
    const fb = await sessionApi.feedback(sq.id, {
      transcript: contextText || text,
      question_dimension: currentQuestion.value?.dimension || '',
      question_content: currentQuestion.value?.content || '',
    })
    aiTyping.value = false
    // 反馈挂在最后一条 me 消息上
    const last = chat.value[chat.value.length - 1]
    if (last && last.who === 'me') last.feedback = fb
    scrollBottom()

    // 决定是否追问
    const canFollowup = (flow.enableFollowup !== false)
      && followupCount.value < MAX_FOLLOWUP
      && fb?.followup
    if (canFollowup) {
      followupCount.value++
      stage.value = 'followup'
      await aiSay(fb.followup, 'followup')
    } else {
      await nextQuestion()
    }
  } catch (e) {
    aiTyping.value = false
    message.warning('AI 分析暂不可用，已进入下一题')
    await nextQuestion()
  }
}

async function nextQuestion() {
  if (recording.value) stopRecord(false)
  await submitCurrent()
}

async function submitCurrent() {
  const sq = props.questions?.[qIndex.value]
  if (!sq) return
  const parts = []
  if (mainAnswer.value) parts.push(`【主问题】\n${mainAnswer.value}`)
  followupAnswers.value.forEach((t, i) => parts.push(`【追问 ${i + 1}】\n${t}`))
  if (!parts.length) {
    message.warning('请先回答再进入下一题')
    return
  }
  submitting.value = true
  try {
    await sessionApi.submitAnswer(props.sessionId, sq.id, {
      transcript: parts.join('\n\n'), audio_url: '',
      duration_ms: parts.join('').length * 400,
    })
    if (qIndex.value < props.questions.length - 1) {
      message.success(`第 ${qIndex.value + 1} 题完成`)
      qIndex.value++
      await startQuestion()
    } else {
      const res = await sessionApi.finish(props.sessionId)
      flow.setReport(res.report_id)
      message.success('面试完成，报告已生成')
      router.push(`/report/${res.report_id}`)
    }
  } catch (e) {
    message.error('提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

function skipFollowup() {
  if (!mainAnswer.value) { message.warning('请先回答主问题'); return }
  nextQuestion()
}

// —— 录音 ——
function toggleTextMode() {
  textMode.value = !textMode.value
  if (textMode.value && recording.value) stopRecord(false)
}

function toggleRecord() {
  if (aiTyping.value || submitting.value) return
  if (!awaitingAnswer.value) { message.info('请先等待面试官提问'); return }
  if (recording.value) stopRecord(true)
  else startRecord()
}

function upsertLive(text) {
  liveText = text
  const arr = chat.value
  const last = arr[arr.length - 1]
  if (last && last.who === 'me' && last.live) {
    last.text = text
    last.ts = fmt(recSecs.value)
  } else {
    arr.push({ who: 'me', text, ts: fmt(recSecs.value), live: true })
  }
  updateMetrics(text, recSecs.value)
  scrollBottom()
}

function finalizeLive() {
  const arr = chat.value
  const last = arr[arr.length - 1]
  if (last && last.who === 'me' && last.live) {
    last.live = false
    if (!last.text) arr.pop()
  }
  scrollBottom()
}

async function startRecord() {
  recording.value = true
  recSecs.value = 0
  committedText = ''
  liveText = ''
  recTimer = setInterval(() => {
    recSecs.value++
    if (recSecs.value > 240) { message.info('单题回答建议不超过 4 分钟'); stopRecord(true) }
  }, 1000)
  if (textMode.value) return

  try {
    asrMode.value = 'ifly'
    asrClient = createAsrClient({
      getToken: () => localStorage.getItem('mockwise_token'),
      onPartial: (t) => upsertLive(committedText + t),
      onFinal: (t) => {
        if (t) committedText += t
        upsertLive(committedText)
      },
      onError: (err) => {
        if (err?.code === 'not_configured' || err?.message === 'ASR_UNAVAILABLE') {
          fallbackToText('语音服务不可用，已切换文字模式')
        } else if (recording.value && err?.code === 'disconnect') {
          // 转写中途断线：保留已转写内容，自动降级到文字作答，避免静默丢失
          fallbackToText('转写连接中断，已保留已转写内容并切换文字模式')
        }
      },
    })
    await asrClient.start()
  } catch (e) {
    const TIPS = {
      MIC_DENIED: '麦克风权限被拒绝：请在浏览器地址栏允许麦克风后重试，或改用文字作答',
      MIC_NOT_FOUND: '未检测到麦克风设备，可改用文字作答',
      MIC_BUSY: '麦克风被占用，可改用文字作答',
      MIC_INSECURE: '请使用 http://localhost:5173 访问（IP 访问会禁用麦克风）',
    }
    fallbackToText(TIPS[e?.message] || '语音启动失败，可改用文字作答')
  }
}

function fallbackToText(tip) {
  if (asrClient) { asrClient.dispose(); asrClient = null }
  recording.value = false
  clearInterval(recTimer)
  textMode.value = true
  message.warning({ content: tip, duration: 5 })
}

async function stopRecord(finishAnswer) {
  recording.value = false
  clearInterval(recTimer)
  if (asrClient) {
    const c = asrClient
    asrClient = null
    // 先等讯飞 final 落地（内部最多等 3s），再定型与提交，避免重复/空文本
    try { await c.stop() } catch { /* ignore */ }
    try { c.dispose() } catch { /* ignore */ }
  }
  const myText = committedText || liveText
  finalizeLive()
  if (finishAnswer && myText) onMyAnswer(myText, recSecs.value)
}

function sendText() {
  const t = textInput.value.trim()
  if (!t || !awaitingAnswer.value) return
  pushChat({ who: 'me', text: t, ts: fmt(recSecs.value) })
  textInput.value = ''
  onMyAnswer(t, Math.max(recSecs.value, 20))
}

// questions 由父组件异步创建 session 后填充，watch 兜住时序
let started = false
watch(() => props.questions.length, (n) => {
  if (n && !started) { started = true; startQuestion() }
}, { immediate: true })

onUnmounted(() => {
  clearInterval(recTimer)
  if (asrClient) { asrClient.dispose(); asrClient = null }
})
</script>

<style scoped>
.semi-layout { display: grid; grid-template-columns: 300px 1fr 280px; gap: 18px; }

.side-card { display: flex; flex-direction: column; gap: 14px; }
.interviewer {
  display: flex; gap: 10px; align-items: center;
  padding: 12px; background: var(--bg); border-radius: 12px;
}
.avatar {
  width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 16px;
}
.i-name { font-size: 13px; font-weight: 700; }
.i-bio { font-size: 11px; color: var(--text-3); }
.progress-block { display: flex; flex-direction: column; gap: 6px; }
.p-row { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-2); }
.bar-shell { height: 8px; background: var(--border-soft); border-radius: 4px; overflow: hidden; }
.bar-shell > span { display: block; height: 100%; background: var(--success); border-radius: 4px; transition: width .3s; }

.chat-card { display: flex; flex-direction: column; padding: 18px; min-height: 560px; }
.chat-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.chat-stream { flex: 1; overflow-y: auto; max-height: 480px; padding-right: 6px; }
.msg-row { display: flex; gap: 10px; margin-bottom: 16px; }
.msg-row.me { flex-direction: row-reverse; }
.msg-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 13px;
}
.msg-body { max-width: 80%; display: flex; flex-direction: column; gap: 5px; }
.msg-row.me .msg-body { align-items: flex-end; }
.msg-meta { font-size: 11px; color: var(--text-3); }
.msg-bubble {
  padding: 12px 15px; border-radius: 12px; font-size: 13px; line-height: 1.65;
  background: #F5F6F9; color: var(--text-1); white-space: pre-wrap;
}
.msg-bubble.me { background: var(--primary); color: #fff; }
.followup-tag {
  display: inline-block; padding: 1px 8px; margin-right: 6px;
  background: var(--warning-mid); color: var(--warning);
  border-radius: 10px; font-size: 11px; font-weight: 700;
}
.msg-bubble.typing { display: flex; gap: 5px; padding: 14px 18px; }
.msg-bubble.typing span {
  width: 7px; height: 7px; border-radius: 50%; background: var(--text-3);
  animation: blink 1.2s infinite;
}
.msg-bubble.typing span:nth-child(2) { animation-delay: .2s; }
.msg-bubble.typing span:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%, 60%, 100% { opacity: .3; } 30% { opacity: 1; } }

/* AI 反馈卡片 */
.fb-card {
  background: linear-gradient(135deg, #EEF2FF 0%, #F0F9FF 100%);
  border: 1px solid #C7D2FE; border-radius: 12px; padding: 12px 14px;
  font-size: 12px; line-height: 1.6; max-width: 100%;
}
.fb-head { display: flex; align-items: center; gap: 8px; font-weight: 700; color: var(--primary); margin-bottom: 6px; }
.ai-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 6px;
  background: var(--primary); color: #fff; font-weight: 700; font-size: 11px;
}
.fb-understanding { color: var(--text-1); margin-bottom: 6px; }
.fb-list { margin: 4px 0 0; padding-left: 18px; }
.fb-list li { color: var(--text-2); margin-bottom: 3px; }
.fb-list.good li { color: var(--success); }

.chat-input {
  border-top: 1px solid var(--border-soft); padding-top: 14px; margin-top: 10px;
  display: flex; flex-direction: column; gap: 8px;
}
.input-btns { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.action-hint { font-size: 12px; color: var(--text-3); }
.mic-btn {
  padding: 11px 20px; border-radius: var(--r-pill);
  background: var(--primary); color: #fff; border: none;
  display: inline-flex; align-items: center; gap: 8px; font-weight: 600; cursor: pointer;
}
.mic-btn.recording { background: var(--danger); }
.mic-btn:disabled { opacity: .5; cursor: not-allowed; }

.metric-card { display: flex; flex-direction: column; gap: 12px; }
.metric-row { display: flex; justify-content: space-between; align-items: center; }
.metric-row .n { font-size: 13px; color: var(--text-2); }
.metric-row .v { font-size: 13px; font-weight: 700; }

@media (max-width: 1100px) { .semi-layout { grid-template-columns: 1fr; } }
</style>
