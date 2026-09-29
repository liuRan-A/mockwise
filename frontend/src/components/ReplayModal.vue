<template>
  <a-modal
    :open="open"
    @update:open="$emit('update:open', $event)"
    :width="960"
    :footer="null"
    :title="null"
    :closable="false"
    class="replay-modal"
    destroyOnClose
  >
    <div class="replay-shell" v-if="session">
      <!-- 顶部：标题 + 关闭 -->
      <div class="replay-head">
        <div>
          <span class="mw-tag" :class="formTagClass">{{ session.form_label }}</span>
          <span class="r-title">{{ session.set_name }}</span>
          <span class="r-sub">场次 #{{ session.id }} · {{ session.user_name }} · {{ session.started_at }}</span>
        </div>
        <button class="close-btn" @click="$emit('update:open', false)" aria-label="关闭">×</button>
      </div>

      <div class="replay-body">
        <!-- 左：视频 / 音频播放区 -->
        <div class="player-card">
          <h4 class="card-title">录像 / 录音回放</h4>
          <!-- 视频优先，没有则降级到音频，再降级到"已保存"占位 -->
          <div class="player-window">
            <template v-if="currentQ?.video_url">
              <video
                ref="videoEl"
                :src="currentQ.video_url"
                controls
                class="player-media"
              ></video>
            </template>
            <template v-else-if="currentQ?.audio_url">
              <div class="audio-stage">
                <div class="audio-icon">
                  <svg viewBox="0 0 24 24" width="40" height="40" fill="none">
                    <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3z" stroke="currentColor" stroke-width="1.6"/>
                    <path d="M19 11a7 7 0 0 1-14 0M12 18v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
                  </svg>
                </div>
                <audio
                  ref="audioEl"
                  :src="currentQ.audio_url"
                  controls
                  class="player-audio"
                ></audio>
              </div>
            </template>
            <template v-else>
              <div class="player-mask">
                <PlayCircleOutlined style="font-size:48px; color:#fff;" />
                <div class="mask-meta">
                  <div class="mask-title">{{ currentQ ? '本题仅保存转写，未录制音视频' : '请在右侧选择一题查看回放' }}</div>
                  <div class="mask-sub" v-if="currentQ">{{ fmtMs(currentQ.duration_ms) }} · 第 {{ currentQ.seq }} 题</div>
                </div>
              </div>
            </template>
          </div>

          <!-- 倍速 + 上一题 / 下一题 -->
          <div class="speed-row">
            <div class="speed-left">
              <a-radio-group v-model:value="speed" button-style="solid" size="small">
                <a-radio-button value="0.5">0.5x</a-radio-button>
                <a-radio-button value="1">1x</a-radio-button>
                <a-radio-button value="1.5">1.5x</a-radio-button>
                <a-radio-button value="2">2x</a-radio-button>
              </a-radio-group>
            </div>
            <div class="speed-right">
              <a-button size="small" :disabled="!hasPrev" @click="goto(-1)">上一题</a-button>
              <a-button size="small" :disabled="!hasNext" @click="goto(1)">下一题</a-button>
            </div>
          </div>

          <!-- 转写全文（跟当前题同步高亮） -->
          <h4 class="card-title" style="margin-top:14px;">转写全文</h4>
          <div class="transcript" :class="{ empty: !currentLines.length }">
            <div v-if="currentLines.length" class="transcript-inner">
              <div
                v-for="(line, i) in currentLines"
                :key="i"
                class="transcript-line"
                :class="{ active: i === activeLine }"
                @click="seekLine(i)"
              >
                <span class="ts">{{ String(i + 1).padStart(2, '0') }}</span>
                <span>{{ line }}</span>
              </div>
            </div>
            <a-empty v-else description="无转写记录" />
          </div>
        </div>

        <!-- 右：题列表 + 总览 -->
        <div class="side-card">
          <h4 class="card-title">本场概况</h4>
          <div class="metric-row"><span>总分</span><b>{{ session.total_score ? session.total_score.toFixed(1) : '—' }}</b></div>
          <div class="metric-row"><span>形式</span><b>{{ session.form_label }}</b></div>
          <div class="metric-row"><span>状态</span><b>{{ statusLabel(session.status) }}</b></div>
          <div class="metric-row"><span>题数 / 已答</span><b>{{ questions.length }} / {{ answeredCount }}</b></div>
          <div class="metric-row"><span>总时长</span><b>{{ fmtMs(totalDurationMs) }}</b></div>
          <div class="metric-row"><span>转写字数</span><b>{{ totalChars }}</b></div>
          <div class="save-row">
            <a-tag color="green">转写已保存</a-tag>
            <a-tag :color="hasAudio ? 'green' : 'default'">{{ hasAudio ? '录音已保存' : '未保存录音' }}</a-tag>
            <a-tag :color="hasVideo ? 'green' : 'default'">{{ hasVideo ? '录像已保存' : '未保存录像' }}</a-tag>
          </div>

          <h4 class="card-title" style="margin-top:14px;">逐题时间轴</h4>
          <div class="q-list">
            <div
              v-for="q in questions"
              :key="q.id"
              class="q-item"
              :class="{ active: q.id === currentQId, done: q.status === 'done' }"
              @click="selectQuestion(q.id)"
            >
              <div class="q-no">#{{ q.seq }}</div>
              <div class="q-text">{{ q.question_content || '(未命名)' }}</div>
              <div class="q-meta">
                <span>{{ q.question_dimension || '考察维度' }}</span>
                <span class="dot">·</span>
                <span>{{ q.status === 'done' ? (q.total_score != null ? q.total_score.toFixed(1) + ' 分' : '已作答') : '未作答' }}</span>
              </div>
              <div class="q-tags">
                <a-tag v-if="q.audio_url" color="cyan">录音</a-tag>
                <a-tag v-if="q.video_url" color="purple">录像</a-tag>
                <a-tag v-if="q.transcript" color="green">转写</a-tag>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <a-spin v-else :spinning="true" />
  </a-modal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import { PlayCircleOutlined } from '@ant-design/icons-vue'
import { adminApi } from '@/api'

const props = defineProps({
  open: { type: Boolean, default: false },
  sessionId: { type: Number, default: null },
})
defineEmits(['update:open'])

const session = ref(null)
const questions = ref([])
const currentQId = ref(null)
const speed = ref('1')
const videoEl = ref(null)
const audioEl = ref(null)
const activeLine = ref(0)

const currentQ = computed(() => questions.value.find(q => q.id === currentQId.value))
const currentLines = computed(() => {
  const t = (currentQ.value?.transcript || '').trim()
  if (!t) return []
  // 按句子切分（。！？；\n），去掉空段
  return t.split(/(?<=[。！？；\n])|(?<=\.\s)|(?<=\?\s)|(?<=!\s)/).map(s => s.trim()).filter(Boolean)
})
const answeredCount = computed(() => questions.value.filter(q => q.status === 'done').length)
const totalDurationMs = computed(() => questions.value.reduce((s, q) => s + (q.duration_ms || 0), 0))
const totalChars = computed(() => questions.value.reduce((s, q) => s + (q.transcript || '').length, 0))
const hasAudio = computed(() => questions.value.some(q => q.audio_url))
const hasVideo = computed(() => questions.value.some(q => q.video_url))
const hasPrev = computed(() => {
  const idx = questions.value.findIndex(q => q.id === currentQId.value)
  return idx > 0
})
const hasNext = computed(() => {
  const idx = questions.value.findIndex(q => q.id === currentQId.value)
  return idx >= 0 && idx < questions.value.length - 1
})
const formTagClass = computed(() => ({
  structured: 'blue', group: 'purple', semi: 'cyan',
}[session.value?.form_type] || 'orange'))

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

async function load() {
  if (!props.sessionId) return
  try {
    const data = await adminApi.sessionDetail(props.sessionId)
    session.value = data.session
    questions.value = data.questions || []
    currentQId.value = questions.value.find(q => q.status === 'done')?.id
      || questions.value[0]?.id
      || null
  } catch (e) {
    message.error('加载回放失败')
  }
}

function selectQuestion(id) {
  currentQId.value = id
  activeLine.value = 0
  nextTick(applySpeed)
}

function goto(delta) {
  const idx = questions.value.findIndex(q => q.id === currentQId.value)
  const next = questions.value[idx + delta]
  if (next) selectQuestion(next.id)
}

function seekLine(i) {
  activeLine.value = i
  // 估算时间 = (i / 总行数) * 总时长
  const total = currentLines.value.length || 1
  const dur = (currentQ.value?.duration_ms || 0) / 1000
  const seekTo = Math.max(0, (i / total) * dur)
  if (videoEl.value) try { videoEl.value.currentTime = seekTo; videoEl.value.play().catch(() => {}) } catch {}
  if (audioEl.value) try { audioEl.value.currentTime = seekTo; audioEl.value.play().catch(() => {}) } catch {}
}

function applySpeed() {
  const r = parseFloat(speed.value) || 1
  if (videoEl.value) videoEl.value.playbackRate = r
  if (audioEl.value) audioEl.value.playbackRate = r
}

watch(speed, applySpeed)
watch(() => props.sessionId, (v) => { if (v) load() })
watch(() => props.open, (v) => { if (v) load() })
</script>

<style scoped>
.replay-modal :deep(.ant-modal-body) { padding: 0; }
.replay-shell { display: flex; flex-direction: column; }
.replay-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px; border-bottom: 1px solid var(--border-soft);
}
.r-title { font-size: 16px; font-weight: 700; margin-left: 6px; }
.r-sub { font-size: 12px; color: var(--text-3); margin-left: 12px; }
.close-btn {
  border: none; background: transparent; font-size: 24px;
  width: 36px; height: 36px; border-radius: 8px; cursor: pointer;
  color: var(--text-3);
}
.close-btn:hover { background: var(--bg); color: var(--text-1); }

.replay-body {
  display: grid; grid-template-columns: 1.4fr 1fr;
  gap: 0; min-height: 540px;
}
.player-card {
  padding: 18px 22px; border-right: 1px solid var(--border-soft);
  display: flex; flex-direction: column;
}
.side-card {
  padding: 18px 22px;
  max-height: 600px; overflow-y: auto;
}
.card-title { margin: 0 0 12px; font-size: 14px; font-weight: 700; }

.player-window {
  position: relative; width: 100%;
  aspect-ratio: 16 / 9;
  background: linear-gradient(135deg, #2A2F4A, #1B1E33);
  border-radius: 12px; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
}
.player-media { width: 100%; height: 100%; object-fit: contain; background: #000; }
.player-audio { width: 92%; }
.audio-stage {
  width: 100%; height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 18px;
  background: radial-gradient(ellipse at center, rgba(126, 113, 219, .25), transparent 65%);
  color: #fff;
}
.audio-icon {
  width: 96px; height: 96px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(255, 255, 255, 0.25);
}
.player-mask {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; color: #fff; text-align: center; padding: 20px;
  background: radial-gradient(ellipse at center, rgba(126, 113, 219, .2), transparent 65%);
}
.mask-meta { text-align: center; }
.mask-title { font-size: 14px; font-weight: 600; }
.mask-sub { font-size: 12px; opacity: .8; margin-top: 4px; }

.speed-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 12px;
}

.transcript {
  flex: 1; min-height: 160px; max-height: 220px;
  overflow-y: auto; padding: 4px 0;
}
.transcript-inner { display: flex; flex-direction: column; gap: 6px; }
.transcript-line {
  display: flex; gap: 10px; padding: 8px 10px; border-radius: 8px;
  font-size: 13px; line-height: 1.6; cursor: pointer;
  transition: background .15s;
}
.transcript-line:hover { background: var(--bg); }
.transcript-line.active { background: var(--primary-soft); color: var(--primary); font-weight: 600; }
.transcript-line .ts {
  flex-shrink: 0; font-size: 11px; color: var(--text-3);
  font-weight: 700; padding-top: 2px;
}
.transcript.empty { display: flex; align-items: center; justify-content: center; }

.metric-row {
  display: flex; justify-content: space-between; padding: 7px 0;
  font-size: 13px; color: var(--text-2);
  border-bottom: 1px dashed var(--border-soft);
}
.metric-row:last-of-type { border-bottom: none; }
.metric-row b { color: var(--text-1); font-weight: 700; }
.save-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }

.q-list { display: flex; flex-direction: column; gap: 8px; }
.q-item {
  padding: 10px 12px; border-radius: 10px; cursor: pointer;
  background: var(--bg); border: 1.5px solid transparent;
  transition: all .15s;
}
.q-item:hover { background: var(--primary-soft); }
.q-item.active { background: var(--primary-soft); border-color: var(--primary); }
.q-item.done { border-left: 3px solid var(--success); }
.q-no { font-size: 11px; color: var(--text-3); font-weight: 700; }
.q-text {
  font-size: 13px; font-weight: 600; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-top: 2px;
}
.q-meta {
  font-size: 11px; color: var(--text-3); margin-top: 4px;
  display: flex; align-items: center; gap: 4px;
}
.q-meta .dot { opacity: .5; }
.q-tags { margin-top: 6px; display: flex; gap: 4px; }

@media (max-width: 900px) {
  .replay-body { grid-template-columns: 1fr; }
  .player-card { border-right: none; border-bottom: 1px solid var(--border-soft); }
}
</style>
