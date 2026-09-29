<template>
  <a-spin :spinning="loading">
    <!-- 顶部：辩题 + 三阶段 -->
    <div class="mw-card topic-card">
      <div class="topic-head">
        <span class="mw-tag orange">无领导小组讨论 · {{ STAGES[stage].label }}</span>
        <div class="stage-tabs">
          <span
            v-for="(s, i) in STAGES" :key="i"
            class="stage-tab" :class="{ active: stage === i, done: stage > i }"
          >{{ i + 1 }}. {{ s.label }}</span>
        </div>
        <span class="mw-chip" :class="{ warning: recording }">{{ recording ? '● 录制中 ' + fmt(recSecs) : '⏱ 已进行 ' + fmt(totalSecs) }}</span>
      </div>
      <div class="topic-title">{{ topic }}</div>
      <div class="topic-hint">{{ STAGES[stage].hint }}</div>
    </div>

    <div class="group-layout">
      <!-- 左：同场候选人 -->
      <aside class="mw-card peers-card">
        <h4 class="card-title">同场候选人（{{ peers.length + 1 }} 人）</h4>
        <div class="peer-item me" :class="{ speaking: speakingName === '你' }">
          <div class="p-avatar" style="background: var(--primary);">你</div>
          <div class="p-info">
            <div class="p-name">你</div>
            <div class="p-bio">认真倾听，争取有效发言</div>
          </div>
        </div>
        <div
          v-for="p in peers" :key="p.id"
          class="peer-item" :class="{ speaking: speakingName === p.name }"
        >
          <div class="p-avatar" :style="{ background: p.color }">{{ (p.name || '?')[0] }}</div>
          <div class="p-info">
            <div class="p-name">
              {{ p.name }}
              <span class="p-style" :style="{ color: p.color }">{{ p.style }}</span>
            </div>
            <div class="p-bio">{{ p.bio }}</div>
          </div>
        </div>
        <div class="q-tip" style="margin-top:12px;">
          发言策略：陈述阶段亮明立场 → 自由讨论争取 2 次以上有效发言 → 总结控制在 1 分钟内
        </div>
      </aside>

      <!-- 中：讨论对话流 -->
      <section class="mw-card chat-card">
        <div class="chat-stream" ref="streamRef">
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.who">
            <div v-if="m.who === 'peer'" class="msg-avatar" :style="{ background: m.color }">{{ (m.name || '?')[0] }}</div>
            <div class="msg-body">
              <div class="msg-meta">
                <template v-if="m.who === 'peer'">
                  {{ m.name }} · {{ m.style }}
                  <span v-if="m.replyTo" class="reply-to">↳ 回应 {{ m.replyTo }}</span>
                </template>
                <template v-else-if="m.who === 'me'">你 · {{ m.ts }}</template>
                <template v-else>系统提示</template>
              </div>
              <div
                class="msg-bubble" :class="m.who"
                :style="m.who === 'peer' ? { borderLeft: '3px solid ' + m.color } : {}"
              >{{ m.text }}<span v-if="m.streaming" class="cursor">▍</span></div>
            </div>
          </div>
          <div v-if="aiThinking" class="msg-row peer">
            <div class="msg-avatar" style="background:var(--text-3);">…</div>
            <div class="msg-body">
              <div class="msg-meta">{{ speakingName || '候选人' }} · {{ thinkingLabel }}</div>
              <div class="msg-bubble peer typing"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>

        <!-- 操作区 -->
        <div class="chat-input">
          <template v-if="stage === 1 && waitingPeer">
            <span class="action-hint">其他候选人正在回应，请稍候…</span>
          </template>
          <template v-else>
            <span class="action-hint">{{ inputHint }}</span>
            <div class="input-btns">
              <a-input-search
                v-if="textMode"
                v-model:value="textInput"
                placeholder="输入你的发言，回车发送"
                enter-button="发送"
                style="flex:1; min-width:220px;"
                @search="sendText"
              />
              <a-button @click="textMode = !textMode">{{ textMode ? '切到语音' : '切到文字' }}</a-button>
              <button class="mic-btn" :class="{ recording }" @click="toggleRecord">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="5" y="2" width="4" height="7" rx="2" fill="#fff"/>
                  <rect x="3" y="7" width="8" height="1.5" rx="0.75" fill="#fff"/>
                </svg>
                {{ recording ? '结束发言' : '举手发言' }}
              </button>
              <a-button v-if="stage === 0" type="primary" :disabled="myTurnStatements === 0" @click="toDebate">
                进入自由讨论 →
              </a-button>
              <a-button v-else-if="stage === 1" type="primary" :disabled="myDebateTurns === 0" @click="toSummary">
                进入总结陈词 →
              </a-button>
              <a-button v-else type="primary" :loading="submitting" :disabled="mySummaryTurns === 0" @click="submitDiscussion">
                提交讨论，生成报告 →
              </a-button>
            </div>
          </template>
        </div>
      </section>

      <!-- 右：我的表现 -->
      <aside class="mw-card my-card">
        <h4 class="card-title">我的讨论表现</h4>
        <div class="metric-row"><span class="n">发言次数</span><span class="v">{{ myMessages.length }}</span></div>
        <div class="metric-row"><span class="n">发言总字数</span><span class="v">{{ totalChars }}</span></div>
        <div class="metric-row"><span class="n">当前阶段</span><span class="v">{{ STAGES[stage].label }}</span></div>
        <div class="metric-row"><span class="n">候选人发言</span><span class="v">{{ peerMessages.length }} 条</span></div>
        <div class="bar-wrap">
          <div class="metric-row" style="margin-bottom:6px;">
            <span class="n">参与度（发言/轮次）</span><span class="v">{{ participation }}%</span>
          </div>
          <div class="bar-shell"><span :style="{ width: participation + '%' }"></span></div>
        </div>
        <div class="bar-wrap">
          <div class="metric-row" style="margin-bottom:6px;">
            <span class="n">对话节奏感</span><span class="v">{{ rhythmScore }}/100</span>
          </div>
          <div class="bar-shell"><span :style="{ width: rhythmScore + '%' }"></span></div>
          <div class="rhythm-hint">{{ rhythmHint }}</div>
        </div>
        <div class="q-tip">
          群面考察：团队协作、逻辑说服、时间控制。避免打断他人，也要抓住发言窗口。
        </div>
      </aside>
    </div>
  </a-spin>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
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

// —— 群面三阶段状态机 ——
const STAGES = [
  { label: '个人陈述', hint: '每位候选人依次亮明立场与理由，每人约 1 分钟。轮到你时点击「举手发言」。' },
  { label: '自由讨论', hint: '交锋环节：反驳他人观点或补充己方论据。每次发言后其他候选人会回应你。' },
  { label: '总结陈词', hint: '候选人依次总结。轮到你时给出最终陈词，随后提交生成报告。' },
]
const stage = ref(0)
const messages = ref([])
const peers = ref([])
const speakingName = ref('')
const aiThinking = ref(false)
const thinkingLabel = ref('正在思考')
const waitingPeer = ref(false)
const submitting = ref(false)

const recording = ref(false)
const textMode = ref(false)
const textInput = ref('')
const recSecs = ref(0)
const totalSecs = ref(0)
let asrClient = null
let committedText = ''          // 已通过讯飞 final 确认、跨会话累计的文本
let liveText = ''               // 界面实时显示文本，作为未拿到 final 时的兜底
let recTimer = null
let totalTimer = null
let streamTimer = null          // 流式呈现定时器

const streamRef = ref(null)

const topic = computed(() => props.questions?.[0]?.question_content || '请讨论：AI 大规模取代初级岗位，对行业发展利大于弊还是弊大于利？')
const sqId = computed(() => props.questions?.[0]?.id)

const myMessages = computed(() => messages.value.filter(m => m.who === 'me'))
const peerMessages = computed(() => messages.value.filter(m => m.who === 'peer'))
const totalChars = computed(() => myMessages.value.reduce((s, m) => s + (m.text || '').length, 0))
const myTurnStatements = computed(() => myMessages.value.length)
const myDebateTurns = computed(() => myMessages.value.filter(m => m.stage === 1).length)
const mySummaryTurns = computed(() => myMessages.value.filter(m => m.stage === 2).length)
const participation = computed(() => Math.min(95, myMessages.value.length * 18 + 8))

// 对话节奏感：综合发言次数 + 回应多样性 + 与你发言的呼应
const rhythmScore = computed(() => {
  const my = myMessages.value.length
  const peer = peerMessages.value.length
  if (my === 0) return 0
  // 候选人之间互相呼应的比例（replyTo != me）
  const peerToPeer = peerMessages.value.filter(m => m.replyTo && m.replyTo !== '你').length
  const ratio = peerToPeer / Math.max(1, peer)
  const base = Math.min(50, my * 12) + Math.min(30, peer * 4) + Math.round(ratio * 20)
  return Math.min(100, base)
})
const rhythmHint = computed(() => {
  if (rhythmScore.value >= 80) return '节奏很好，候选人间互相呼应、你来我往'
  if (rhythmScore.value >= 50) return '节奏还行，多关注场上其他候选人的观点'
  if (myMessages.value.length === 0) return '尚未发言，先「举手发言」亮明立场'
  return '发言偏少，鼓励更主动地参与讨论'
})

const inputHint = computed(() => ({
  0: '轮到你作个人陈述：亮明立场 + 1-2 个理由',
  1: '轮到你发言：可以反驳某位候选人，或补充新论据',
  2: '轮到你总结陈词：概括己方立场 + 一句收尾',
}[stage.value]))

function fmt(s) {
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}

function scrollBottom() {
  nextTick(() => {
    if (streamRef.value) streamRef.value.scrollTop = streamRef.value.scrollHeight
  })
}

function pushMsg(m) {
  messages.value.push(m)
  scrollBottom()
}

function sys(text) {
  pushMsg({ who: 'sys', text, ts: fmt(totalSecs.value) })
}

// —— 流式呈现：按字符节奏"打字"出来，比一次性塞进去更像真人发言 ——
function streamMessage(idx, fullText, perCharMs = 35) {
  if (streamTimer) { clearInterval(streamTimer); streamTimer = null }
  let i = 0
  const m = messages.value[idx]
  if (!m) return Promise.resolve()
  m.streaming = true
  m.text = ''
  return new Promise(resolve => {
    streamTimer = setInterval(() => {
      i++
      m.text = fullText.slice(0, i)
      scrollBottom()
      if (i >= fullText.length) {
        clearInterval(streamTimer); streamTimer = null
        m.streaming = false
        m.text = fullText
        scrollBottom()
        resolve()
      }
    }, perCharMs)
  })
}

// —— 取最近 N 条对话作为上下文，传给后端让候选人能引用 ——
function buildContext(n = 6) {
  return messages.value
    .filter(m => m.who === 'me' || m.who === 'peer')
    .slice(-n)
    .map(m => ({
      who: m.who,
      name: m.name || (m.who === 'me' ? '你' : ''),
      text: (m.text || '').slice(-200),
    }))
}

// —— 思考标签轮播，营造"AI 在组织语言"的过程感 ——
const THINK_LABELS = ['正在听你刚才的发言…', '正在整理回应思路…', '正在组织观点…', '正在打字…']
let thinkTimer = null
function startThinking(name) {
  speakingName.value = name
  aiThinking.value = true
  let i = 0
  thinkingLabel.value = THINK_LABELS[0]
  if (thinkTimer) clearInterval(thinkTimer)
  thinkTimer = setInterval(() => {
    i = (i + 1) % THINK_LABELS.length
    thinkingLabel.value = THINK_LABELS[i]
  }, 600)
}
function stopThinking() {
  aiThinking.value = false
  speakingName.value = ''
  if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
}

// —— AI 候选人发言 ——
async function peerTalk(persona, stageName, extra = {}) {
  startThinking(persona.name)
  try {
    const res = await sessionApi.peerTalk(props.sessionId, {
      stage: stageName,
      persona_id: persona.id,
      stance: persona.stance,
      topic: topic.value,
      target_name: extra.target_name || '',
      other_name: extra.other_name || '',
      user_text: extra.user_text || '',
      recent_context: buildContext(extra.contextN || 6),
      respond_to: extra.respond_to || 'me',
    })
    // 模拟"思考时间"：根据文本长度 + 候选人人设的 aggressiveness 算一个动态延迟
    const thinkingMs = Math.min(2400, 900 + res.text.length * 18 + persona.aggressiveness * 80)
    await new Promise(r => setTimeout(r, thinkingMs))
    stopThinking()
    // 占位先 push 一条 streaming 的消息，按字符呈现
    pushMsg({
      who: 'peer', name: res.name, style: res.style, color: res.color,
      text: '', ts: fmt(totalSecs.value), replyTo: extra.replyTo || '',
      streaming: true,
    })
    const idx = messages.value.length - 1
    // 流式打字速率：每字 30ms（激进派快 22，整合派慢 38）
    const cps = persona.aggressiveness >= 4 ? 22 : persona.aggressiveness <= 2 ? 38 : 30
    await streamMessage(idx, res.text, cps)
  } catch (e) {
    stopThinking()
    const fallback = '这个观点我有不同看法，我认为还是要从行业长期发展的角度来评估。'
    pushMsg({
      who: 'peer', name: persona.name, style: persona.style, color: persona.color,
      text: fallback, ts: fmt(totalSecs.value), replyTo: extra.replyTo || '',
    })
  }
}

function stanceOf(idx) {
  return idx % 2 === 0
    ? '我支持这个命题'
    : '我反对这个命题'
}

// —— 阶段推进 ——
async function startOpening() {
  waitingPeer.value = true
  sys('讨论开始，进入「个人陈述」环节，每位候选人依次发言。')
  const order = [...peers.value]
  for (let i = 0; i < Math.min(2, order.length); i++) {
    await peerTalk(order[i], 'opening')
    await new Promise(r => setTimeout(r, 400))
  }
  waitingPeer.value = false
  sys('轮到你作个人陈述了：点击「举手发言」亮明你的立场和理由。')
}

async function toDebate() {
  // 停止录音：afterMySpeech 内部按当前 stage 定性回应分支（opening），await 保证 stage 尚未被改
  if (recording.value) await stopRecord()
  stage.value = 1
  sys('进入「自由讨论」环节。请围绕辩题交锋，每次发言后其他候选人会针对你的观点回应。')
}

// —— 候选人发言后，AI 候选人针对「你说的原话」回应（三个阶段均触发） ——
async function afterMySpeech(myText) {
  waitingPeer.value = true
  const pool = [...peers.value].sort((a, b) => b.aggressiveness - a.aggressiveness)
  if (stage.value === 0) {
    // 个人陈述后：一位候选人针对你的立场表态
    const p = pool[0]
    await peerTalk(p, 'opening', {
      target_name: '你', user_text: myText,
      replyTo: '你', respond_to: 'me', contextN: 6,
    })
    waitingPeer.value = false
    sys('你的陈述已收到。可以继续补充，或点击「进入自由讨论」。')
  } else if (stage.value === 1) {
    // 自由讨论：候选人之间的「来回」很重要 —— 不只回应你，还要互相呼应
    const responders = pool.slice(0, Math.random() < 0.45 ? 2 : 1)
    for (let i = 0; i < responders.length; i++) {
      // 第 2 位回应者有 50% 概率去回应第 1 位候选人（而不是用户），形成"你来我往"的对话感
      const respondToOtherPeer = responders.length > 1 && i > 0 && Math.random() < 0.5
      if (respondToOtherPeer) {
        const prev = responders[i - 1]
        await peerTalk(responders[i], 'debate', {
          target_name: prev.name, user_text: '',  // 让后端从 context 里抽 prev 的发言
          replyTo: prev.name, respond_to: prev.name, contextN: 8,
        })
      } else {
        const other = responders.find(p => p !== responders[i])
        await peerTalk(responders[i], 'debate', {
          target_name: '你', user_text: myText,
          other_name: other ? other.name : '',
          replyTo: '你', respond_to: 'me', contextN: 8,
        })
      }
      await new Promise(r => setTimeout(r, 350))
    }
    waitingPeer.value = false
    sys('请继续发言，或点击「进入总结陈词」。')
  } else {
    // 总结陈词后：一位候选人针对你的总结收尾
    const p = [...peers.value].sort((a, b) => a.aggressiveness - b.aggressiveness)[0]
    await peerTalk(p, 'summary', {
      target_name: '你', user_text: myText,
      replyTo: '你', respond_to: 'me', contextN: 6,
    })
    waitingPeer.value = false
    sys('所有候选人总结完毕，点击「提交讨论，生成报告」。')
  }
}

async function toSummary() {
  if (recording.value) await stopRecord()
  stage.value = 2
  runSummary()
}

async function runSummary() {
  waitingPeer.value = true
  sys('进入「总结陈词」环节，候选人依次总结。')
  const order = [...peers.value].sort((a, b) => a.aggressiveness - b.aggressiveness)
  for (const p of order.slice(0, 2)) {
    await peerTalk(p, 'summary')
    await new Promise(r => setTimeout(r, 300))
  }
  waitingPeer.value = false
  sys('轮到你了：请给出你的总结陈词，然后点击「提交讨论」。')
}

async function submitDiscussion() {
  if (recording.value) await stopRecord()
  const mine = myMessages.value
  if (!mine.length) { message.warning('请先发言再提交'); return }
  submitting.value = true
  try {
    const parts = []
    for (const st of [0, 1, 2]) {
      const t = myMessages.value.filter(m => m.stage === st).map(m => m.text).join('\n')
      if (t) parts.push(`【${STAGES[st].label}】\n${t}`)
    }
    await sessionApi.submitAnswer(props.sessionId, sqId.value, {
      transcript: parts.join('\n\n'), audio_url: '',
      duration_ms: totalSecs.value * 1000,
    })
    const res = await sessionApi.finish(props.sessionId)
    flow.setReport(res.report_id)
    message.success('群面结束，报告已生成')
    router.push(`/report/${res.report_id}`)
  } catch (e) {
    message.error('提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

// —— 我的发言（语音 / 文字） ——
function toggleRecord() {
  if (waitingPeer.value) { message.info('请等待其他候选人发言完毕'); return }
  if (recording.value) stopRecord()
  else startRecord()
}

function upsertLive(text) {
  liveText = text
  const arr = messages.value
  const last = arr[arr.length - 1]
  if (last && last.who === 'me' && last.live) {
    last.text = text
    last.ts = fmt(recSecs.value)
  } else {
    arr.push({ who: 'me', text, ts: fmt(recSecs.value), live: true, stage: stage.value })
  }
  scrollBottom()
}

function finalizeLive() {
  const arr = messages.value
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
    recSecs.value++; totalSecs.value++
    if (recSecs.value > 180) { message.info('单次发言建议不超过 3 分钟'); stopRecord() }
  }, 1000)

  if (textMode.value) return

  try {
    asrClient = createAsrClient({
      getToken: () => localStorage.getItem('mockwise_token'),
      onPartial: (t) => upsertLive(committedText + t),
      onFinal: (t) => {
        if (t) committedText += t
        upsertLive(committedText)
      },
      onError: (err) => {
        if (err?.code === 'not_configured' || err?.message === 'ASR_UNAVAILABLE') {
          fallbackToText('语音服务不可用，请改用文字发言')
        }
      },
    })
    await asrClient.start()
  } catch (e) {
    const TIPS = {
      MIC_DENIED: '麦克风权限被拒绝：请在浏览器地址栏允许麦克风后重试，或改用文字发言',
      MIC_NOT_FOUND: '未检测到麦克风设备，可改用文字发言',
      MIC_BUSY: '麦克风被占用，可改用文字发言',
      MIC_INSECURE: '请使用 http://localhost:5173 访问（IP 访问会禁用麦克风）',
    }
    fallbackToText(TIPS[e?.message] || '语音启动失败，可改用文字发言')
  }
}

function fallbackToText(tip) {
  if (asrClient) { asrClient.dispose(); asrClient = null }
  recording.value = false
  clearInterval(recTimer)
  textMode.value = true
  message.warning({ content: tip, duration: 5 })
}

async function stopRecord() {
  recording.value = false
  clearInterval(recTimer)
  if (asrClient) {
    const c = asrClient
    asrClient = null
    // 先等讯飞 final 落地（内部最多等 3s），再定型并触发候选人回应，避免重复/空文本
    try { await c.stop() } catch { /* ignore */ }
    try { c.dispose() } catch { /* ignore */ }
  }
  const myText = committedText || liveText
  finalizeLive()
  // 停止后根据当前阶段触发候选人针对你原话的回应
  if (myText) afterMySpeech(myText)
}

function sendText() {
  const t = textInput.value.trim()
  if (!t) return
  if (waitingPeer.value) { message.info('请等待其他候选人发言完毕'); return }
  pushMsg({ who: 'me', text: t, ts: fmt(totalSecs.value), stage: stage.value })
  textInput.value = ''
  afterMySpeech(t)
}

// —— 初始化 ——
let bootStarted = false
async function boot() {
  if (bootStarted || !props.sessionId) return
  bootStarted = true
  // 加载 AI 候选人
  try {
    const list = await sessionApi.peers(props.sessionId)
    peers.value = (list || []).map((p, i) => ({ ...p, stance: stanceOf(i) }))
  } catch { /* 空列表兜底 */ }
  if (!peers.value.length) {
    peers.value = [
      { id: -1, name: '赵启明', style: '激进派', color: '#D8504F', bio: '语速快观点猛', aggressiveness: 5, stance: stanceOf(0) },
      { id: -2, name: '林晚晴', style: '整合派', color: '#2FA36B', bio: '善于归纳共识', aggressiveness: 3, stance: stanceOf(1) },
    ]
  }
  totalTimer = setInterval(() => { if (!recording.value) totalSecs.value++ }, 1000)
  startOpening()
}

// sessionId 可能在父组件异步创建 session 后才就绪，用 watch 兜住时序
watch(() => props.sessionId, (v) => { if (v) boot() }, { immediate: true })

onUnmounted(() => {
  clearInterval(recTimer)
  clearInterval(totalTimer)
  if (streamTimer) { clearInterval(streamTimer); streamTimer = null }
  if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
  if (asrClient) { asrClient.dispose(); asrClient = null }
})
</script>

<style scoped>
.topic-card { padding: 20px 24px; margin-bottom: 18px; display: flex; flex-direction: column; gap: 10px; }
.topic-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.stage-tabs { display: flex; gap: 8px; flex: 1; }
.stage-tab {
  padding: 5px 14px; border-radius: 18px; font-size: 12px; font-weight: 600;
  background: var(--bg); color: var(--text-3); border: 1.5px solid transparent;
}
.stage-tab.active { background: var(--primary-soft); color: var(--primary); border-color: var(--primary); }
.stage-tab.done { color: var(--success); }
.topic-title { font-size: 17px; font-weight: 700; line-height: 1.5; }
.topic-hint { font-size: 12px; color: var(--text-3); }

.group-layout { display: grid; grid-template-columns: 300px 1fr 280px; gap: 18px; }
.card-title { margin: 0 0 12px; font-size: 14px; }

.peers-card { display: flex; flex-direction: column; }
.peer-item {
  display: flex; gap: 10px; align-items: center;
  padding: 10px; border-radius: 12px; margin-bottom: 8px;
  transition: all .2s; border: 1.5px solid transparent;
}
.peer-item.speaking { background: var(--primary-soft); border-color: var(--primary); }
.peer-item.me { background: var(--bg); }
.p-avatar {
  width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 14px;
}
.p-info { min-width: 0; }
.p-name { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.p-style { font-size: 11px; font-weight: 600; }
.p-bio {
  font-size: 11px; color: var(--text-3);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.chat-card { display: flex; flex-direction: column; padding: 18px; min-height: 560px; }
.chat-stream { flex: 1; overflow-y: auto; max-height: 460px; padding-right: 6px; }
.msg-row { display: flex; gap: 10px; margin-bottom: 16px; }
.msg-row.me { flex-direction: row-reverse; }
.msg-row.sys { justify-content: center; }
.msg-row.sys .msg-meta { display: none; }
.msg-row.sys .msg-bubble {
  background: var(--warning-mid); color: var(--warning);
  font-size: 12px; padding: 8px 16px; border-radius: 16px;
}
.msg-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 13px;
}
.msg-body { max-width: 78%; display: flex; flex-direction: column; gap: 5px; }
.msg-row.me .msg-body { align-items: flex-end; }
.msg-meta { font-size: 11px; color: var(--text-3); }
.msg-bubble {
  padding: 11px 15px; border-radius: 12px; font-size: 13px; line-height: 1.65;
  background: #F5F6F9; color: var(--text-1);
}
.msg-bubble.me { background: var(--primary); color: #fff; }
.msg-bubble.typing { display: flex; gap: 5px; padding: 14px 18px; }
.msg-bubble.typing span {
  width: 7px; height: 7px; border-radius: 50%; background: var(--text-3);
  animation: blink 1.2s infinite;
}
.msg-bubble.typing span:nth-child(2) { animation-delay: .2s; }
.msg-bubble.typing span:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%, 60%, 100% { opacity: .3; } 30% { opacity: 1; } }

.chat-input {
  border-top: 1px solid var(--border-soft); padding-top: 14px; margin-top: 10px;
  display: flex; flex-direction: column; gap: 10px;
}
.input-btns { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.action-hint { font-size: 12px; color: var(--text-3); }
.mic-btn {
  padding: 11px 20px; border-radius: var(--r-pill);
  background: var(--primary); color: #fff; border: none;
  display: inline-flex; align-items: center; gap: 8px; font-weight: 600; cursor: pointer;
}
.mic-btn.recording { background: var(--danger); }

.my-card { display: flex; flex-direction: column; gap: 12px; }
.metric-row { display: flex; justify-content: space-between; align-items: center; }
.metric-row .n { font-size: 13px; color: var(--text-2); }
.metric-row .v { font-size: 13px; font-weight: 700; }
.bar-shell { height: 8px; background: var(--border-soft); border-radius: 4px; overflow: hidden; }
.bar-shell > span { display: block; height: 100%; background: var(--success); border-radius: 4px; transition: width .3s; }

@media (max-width: 1100px) { .group-layout { grid-template-columns: 1fr; } }

/* —— 流式打字光标 —— */
.cursor {
  display: inline-block;
  margin-left: 2px;
  color: currentColor;
  opacity: .7;
  animation: cursor-blink 1s steps(2, start) infinite;
}
@keyframes cursor-blink { to { visibility: hidden; } }

/* —— "↳ 回应 XX" 标签 —— */
.reply-to {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 8px;
  font-size: 10px;
  font-weight: 600;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.18);
  color: var(--text-3);
}

/* —— 节奏感条下方说明 —— */
.rhythm-hint {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 6px;
  line-height: 1.5;
}
</style>
