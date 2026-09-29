/**
 * 科大讯飞实时语音转写客户端（经后端 /ws/asr 代理）
 *
 * 链路: 麦克风 → AudioContext 采集 → 重采样 16k/16bit/mono PCM
 *      → 1280B(40ms) 帧 → WebSocket → 后端 → 讯飞 IAT → 实时文本
 *
 * 讯飞单会话上限 60s，这里 55s 自动续接新会话，对上层无感知。
 */

const TARGET_RATE = 16000
const FRAME_BYTES = 1280        // 40ms @ 16k 16bit mono
const SESSION_MAX_MS = 55000    // 提前 5s 续接，避免撞 60s 上限

export function createAsrClient({ getToken, onPartial, onFinal, onError, onStatus }) {
  let ws = null
  let audioCtx = null
  let micStream = null
  let processor = null
  let sourceNode = null
  let muteGain = null              // 静音 sink：让 ScriptProcessor 持续触发但不回放声音，避免回声

  let sessionTimer = null
  let stopWaiter = null          // resolve on server 'final' during stop
  let active = false             // 整段录音是否进行中
  let sessionReady = false       // 当前讯飞会话是否 ready
  let connectError = null        // 讯飞会话建立失败信息
  let disposed = false

  let pendingPcm = new Uint8Array(0)

  // —— WebSocket ——————————————————————————————
  function wsUrl() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/ws/asr?token=${encodeURIComponent(getToken() || '')}`
  }

  function openWs() {
    return new Promise((resolve, reject) => {
      ws = new WebSocket(wsUrl())
      ws.binaryType = 'arraybuffer'
      ws.onopen = () => resolve()
      ws.onerror = () => reject(new Error('WS_CONNECT_FAIL'))
      ws.onmessage = (ev) => handleServerMsg(ev.data)
      ws.onclose = () => {
        sessionReady = false
        if (active) {
          active = false
          cleanupAudio()
          onError && onError({ code: 'disconnect', message: '转写连接已断开' })
        }
      }
    })
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj))
  }

  function handleServerMsg(raw) {
    let msg
    try { msg = JSON.parse(raw) } catch { return }
    switch (msg.type) {
      case 'ready':
        sessionReady = true
        break
      case 'partial':
        onPartial && onPartial(msg.text || '')
        break
      case 'final':
        if (stopWaiter) { stopWaiter(msg.text || ''); stopWaiter = null }
        onFinal && onFinal(msg.text || '')
        break
      case 'error':
        if (msg.code === 'connect' || msg.code === 'not_configured') connectError = msg.message
        onError && onError(msg)
        break
    }
  }

  // —— 音频采集 ——————————————————————————————
  async function startMic() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      // http 或 IP 访问时浏览器禁用麦克风（localhost 除外）
      throw new Error('MIC_INSECURE')
    }
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: { ideal: TARGET_RATE },
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
    } catch (e) {
      const name = e?.name || ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        throw new Error('MIC_DENIED')       // 用户或浏览器设置拒绝了权限
      }
      if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        throw new Error('MIC_NOT_FOUND')    // 没有麦克风设备
      }
      if (name === 'NotReadableError' || name === 'TrackStartError') {
        throw new Error('MIC_BUSY')         // 设备被其他应用占用
      }
      throw new Error('MIC_ERROR')
    }
    audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    sourceNode = audioCtx.createMediaStreamSource(micStream)
    processor = audioCtx.createScriptProcessor(4096, 1, 1)
    processor.onaudioprocess = (e) => {
      if (!active || !sessionReady) return
      const f32 = e.inputBuffer.getChannelData(0)
      const pcm = floatTo16(downsample(f32, audioCtx.sampleRate))
      pushPcm(pcm)
    }
    sourceNode.connect(processor)
    // ScriptProcessor 必须连到 destination 才会持续触发 onaudioprocess，
    // 但不能直连（会把麦克风声音回放到扬声器，产生回声导致转写叠字）。
    // 这里挂一个 gain=0 的静音节点做"扬声器"，既保证计算触发又不产生声音输出。
    muteGain = audioCtx.createGain()
    muteGain.gain.value = 0
    processor.connect(muteGain)
    muteGain.connect(audioCtx.destination)
  }

  function cleanupAudio() {
    try { processor && (processor.onaudioprocess = null, processor.disconnect()) } catch { /* */ }
    try { sourceNode && sourceNode.disconnect() } catch { /* */ }
    try { muteGain && muteGain.disconnect() } catch { /* */ }
    try { micStream && micStream.getTracks().forEach(t => t.stop()) } catch { /* */ }
    try { audioCtx && audioCtx.close() } catch { /* */ }
    processor = null; sourceNode = null; muteGain = null; micStream = null; audioCtx = null
    pendingPcm = new Uint8Array(0)
  }

  function downsample(f32, srcRate) {
    if (srcRate === TARGET_RATE) return f32
    const ratio = srcRate / TARGET_RATE
    const len = Math.floor(f32.length / ratio)
    const out = new Float32Array(len)
    for (let i = 0; i < len; i++) {
      const idx = i * ratio
      const i0 = Math.floor(idx)
      const i1 = Math.min(i0 + 1, f32.length - 1)
      const frac = idx - i0
      out[i] = f32[i0] * (1 - frac) + f32[i1] * frac
    }
    return out
  }

  function floatTo16(f32) {
    const buf = new ArrayBuffer(f32.length * 2)
    const view = new DataView(buf)
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]))
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    return new Uint8Array(buf)
  }

  function pushPcm(bytes) {
    const merged = new Uint8Array(pendingPcm.length + bytes.length)
    merged.set(pendingPcm)
    merged.set(bytes, pendingPcm.length)
    pendingPcm = merged
    while (pendingPcm.length >= FRAME_BYTES) {
      const frame = pendingPcm.slice(0, FRAME_BYTES)
      pendingPcm = pendingPcm.slice(FRAME_BYTES)
      ws.send(frame.buffer)
    }
  }

  // —— 会话生命周期 ————————————————————————————
  async function startSession() {
    sessionReady = false
    connectError = null
    send({ type: 'start' })
    // 等 ready（最多 5s；连接出错立即失败）
    await new Promise((resolve, reject) => {
      const t0 = Date.now()
      const iv = setInterval(() => {
        if (sessionReady) { clearInterval(iv); resolve() }
        else if (connectError) { clearInterval(iv); reject(new Error('SESSION_ERROR')) }
        else if (Date.now() - t0 > 5000) { clearInterval(iv); reject(new Error('SESSION_TIMEOUT')) }
      }, 50)
    })
    clearTimeout(sessionTimer)
    sessionTimer = setTimeout(() => renewSession(), SESSION_MAX_MS)
  }

  async function renewSession() {
    // 55s 到：结束当前会话拿 final，立即开新会话继续
    if (!active) return
    send({ type: 'stop' })
    clearTimeout(sessionTimer)
    try {
      await startSession()
      onStatus && onStatus('renewed')
    } catch { /* 网络抖动时由 onclose 兜底 */ }
  }

  // —— 对外接口 ——————————————————————————————
  async function start() {
    disposed = false
    active = true
    try {
      await openWs()
      await startSession()
      await startMic()
      onStatus && onStatus('recording')
    } catch (e) {
      active = false
      cleanupAudio()
      try { ws && ws.close() } catch { /* */ }
      if (e.message === 'WS_CONNECT_FAIL') {
        throw new Error('ASR_UNAVAILABLE')
      }
      throw e
    }
  }

  async function stop() {
    if (!active) return
    active = false
    clearTimeout(sessionTimer)
    cleanupAudio()
    // 通知服务端结束当前会话，等服务端 final（最多 3s）
    const gotFinal = new Promise((resolve) => { stopWaiter = resolve })
    send({ type: 'stop' })
    await Promise.race([gotFinal, new Promise(r => setTimeout(r, 3000))])
    stopWaiter = null
    try { ws && ws.close() } catch { /* */ }
    ws = null
    sessionReady = false
    onStatus && onStatus('stopped')
  }

  function dispose() {
    disposed = true
    active = false
    clearTimeout(sessionTimer)
    cleanupAudio()
    try { ws && ws.close() } catch { /* */ }
    ws = null
  }

  return { start, stop, dispose, isActive: () => active }
}
