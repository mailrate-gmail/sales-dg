import { useEffect, useMemo, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

type Role = 'self' | 'customer' | 'other' | 'unknown'
type Page = 'new' | 'history' | 'settings' | 'room'
type Theme = 'dark' | 'light' | 'blue'

interface Participant {
  id: string
  name: string
  role: Role
  need_reply: boolean
  display_color: string
  voiceprint_file?: string
  remark: string
}

interface Message {
  id: string
  session_id: string
  participant_id?: string | null
  speaker_identity_id?: string | null
  speaker_name: string
  role: Role
  text: string
  speaker_score?: number
  need_reply: boolean
  ai_suggestion?: string
  corrected: boolean
}

interface SessionDetail {
  id: string
  title: string
  goal: string
  started_at: string
  ended_at?: string | null
  messages: Message[]
  summary?: string | null
}

interface SessionSummary {
  id: string
  title: string
  goal: string
  started_at: string
  ended_at?: string | null
  message_count: number
  has_summary: boolean
}

interface ModelConfig {
  llm_provider: string
  llm_model: string
  llm_base_url: string
  llm_api_key: string
  llm_timeout_seconds: number
  whisper_model: string
  whisper_device: string
  whisper_compute_type: string
  speaker_threshold: number
  energy_threshold: number
  silence_duration_ms: number
  min_speech_duration_ms: number
}

interface RecognizedSpeaker {
  id: string
  name: string
  role: Role
  count: number
  latestScore?: number
}

const defaultConfig: ModelConfig = {
  llm_provider: 'deepseek',
  llm_model: 'deepseek-chat',
  llm_base_url: 'https://api.deepseek.com',
  llm_api_key: '',
  llm_timeout_seconds: 30,
  whisper_model: 'small',
  whisper_device: 'cpu',
  whisper_compute_type: 'int8',
  speaker_threshold: 0.7,
  energy_threshold: 0.02,
  silence_duration_ms: 800,
  min_speech_duration_ms: 1000,
}

export function App() {
  const [page, setPage] = useState<Page>('new')
  const [theme, setTheme] = useState<Theme>('dark')
  const [customerName, setCustomerName] = useState('')
  const [goal, setGoal] = useState('了解客户当前业务痛点，并推动下一次需求调研。')
  const [sessionId, setSessionId] = useState<string>('')
  const [sessionTitle, setSessionTitle] = useState('')
  const [participants, setParticipants] = useState<Participant[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({})
  const [latestSuggestion, setLatestSuggestion] = useState('')
  const [summary, setSummary] = useState('')
  const [recording, setRecording] = useState(false)
  const [energyLevel, setEnergyLevel] = useState(0)
  const [config, setConfig] = useState<ModelConfig>(defaultConfig)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const speechActiveRef = useRef(false)
  const segmentStartedAtRef = useRef(0)
  const lastVoiceAtRef = useRef(0)
  const activeSessionIdRef = useRef('')
  const configRef = useRef(config)

  useEffect(() => {
    configRef.current = config
  }, [config])

  useEffect(() => {
    document.body.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    loadParticipants()
    loadConfig()
    loadSessions()
  }, [])

  const recognizedSpeakers = useMemo(() => {
    const map = new Map<string, RecognizedSpeaker>()
    for (const message of messages) {
      const id = getSpeakerIdentity(message)
      const existing = map.get(id)
      const displayName = speakerNames[id] ?? (message.speaker_name === '未知说话人' ? '' : message.speaker_name)
      if (existing) {
        existing.count += 1
        existing.latestScore = message.speaker_score
        if (displayName) existing.name = displayName
      } else {
        map.set(id, {
          id,
          name: displayName,
          role: message.role,
          count: 1,
          latestScore: message.speaker_score,
        })
      }
    }
    return Array.from(map.values())
  }, [messages, speakerNames])

  function getSpeakerIdentity(message: Message) {
    return message.speaker_identity_id || message.participant_id || `voice_${message.id}`
  }

  async function loadParticipants() {
    const res = await fetch(`${API_BASE}/api/participants`)
    if (res.ok) setParticipants(await res.json())
  }

  async function loadSessions() {
    const res = await fetch(`${API_BASE}/api/sessions`)
    if (res.ok) setSessions(await res.json())
  }

  async function loadConfig() {
    const res = await fetch(`${API_BASE}/api/config`)
    if (res.ok) setConfig(await res.json())
  }

  async function saveConfig() {
    const res = await fetch(`${API_BASE}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    if (!res.ok) {
      alert('模型配置保存失败')
      return
    }
    setConfig(await res.json())
    alert('模型配置已保存')
  }

  async function enterMeeting() {
    if (!customerName.trim()) {
      alert('请输入客户名称')
      return
    }
    if (!goal.trim()) {
      alert('请输入会晤目标')
      return
    }

    const res = await fetch(`${API_BASE}/api/meetings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_name: customerName.trim(), goal }),
    })
    const data: SessionDetail = await res.json()
    setSessionId(data.id)
    activeSessionIdRef.current = data.id
    setSessionTitle(data.title)
    setMessages([])
    setSpeakerNames({})
    setLatestSuggestion('')
    setSummary('')
    setPage('room')
    await loadSessions()
  }

  async function openSession(id: string) {
    const res = await fetch(`${API_BASE}/api/sessions/${id}`)
    if (!res.ok) {
      alert('会议不存在')
      return
    }
    const data: SessionDetail = await res.json()
    setSessionId(data.id)
    activeSessionIdRef.current = data.id
    setSessionTitle(data.title)
    setGoal(data.goal)
    setMessages(data.messages || [])
    setSummary(data.summary || '')
    setLatestSuggestion([...data.messages].reverse().find((m) => m.ai_suggestion)?.ai_suggestion || '')
    setSpeakerNames({})
    setPage('room')
  }

  async function startRecording() {
    if (!sessionId) {
      alert('请先新建会议并进入会议室')
      return
    }

    activeSessionIdRef.current = sessionId
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)

    audioContextRef.current = audioContext
    analyserRef.current = analyser

    const recorder = new MediaRecorder(stream)
    mediaRecorderRef.current = recorder
    chunksRef.current = []
    speechActiveRef.current = false

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0 && speechActiveRef.current) {
        chunksRef.current.push(event.data)
      }
    }

    recorder.onstop = async () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
      await flushSpeechSegment()
      await audioContext.close()
      stream.getTracks().forEach((track) => track.stop())
      setEnergyLevel(0)
    }

    recorder.start(250)
    setRecording(true)
    monitorEnergy()
  }

  function monitorEnergy() {
    const analyser = analyserRef.current
    if (!analyser) return

    const buffer = new Float32Array(analyser.fftSize)
    analyser.getFloatTimeDomainData(buffer)
    const rms = Math.sqrt(buffer.reduce((sum, value) => sum + value * value, 0) / buffer.length)
    const now = Date.now()
    const activeConfig = configRef.current

    setEnergyLevel(rms)

    if (rms >= activeConfig.energy_threshold) {
      lastVoiceAtRef.current = now
      if (!speechActiveRef.current) {
        speechActiveRef.current = true
        segmentStartedAtRef.current = now
        chunksRef.current = []
      }
    }

    if (speechActiveRef.current) {
      const silenceMs = now - lastVoiceAtRef.current
      const speechMs = now - segmentStartedAtRef.current
      if (silenceMs >= activeConfig.silence_duration_ms && speechMs >= activeConfig.min_speech_duration_ms) {
        void flushSpeechSegment()
      }
    }

    animationFrameRef.current = requestAnimationFrame(monitorEnergy)
  }

  async function flushSpeechSegment() {
    if (!speechActiveRef.current || chunksRef.current.length === 0) {
      speechActiveRef.current = false
      chunksRef.current = []
      return
    }

    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    speechActiveRef.current = false
    chunksRef.current = []
    await uploadAudioSegment(blob)
  }

  async function uploadAudioSegment(blob: Blob) {
    const activeSessionId = activeSessionIdRef.current || sessionId
    if (!activeSessionId) return

    const form = new FormData()
    form.append('session_id', activeSessionId)
    form.append('file', blob, 'speech.webm')
    try {
    const res = await fetch(`${API_BASE}/api/meetings/${activeSessionId}/audio`, { method: 'POST', body: form })
      if (!res.ok) return
      const message: Message = await res.json()
      setMessages((items) => [...items, message])
      if (message.ai_suggestion) setLatestSuggestion(message.ai_suggestion)
      await loadSessions()
    } catch (error) {
      console.error(error)
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  async function applySpeakerName(identityId: string) {
    const name = speakerNames[identityId]?.trim()
    if (!sessionId || !name) return

    const res = await fetch(`${API_BASE}/api/meetings/${sessionId}/speakers/${identityId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speaker_name: name, role: 'customer', need_reply: true }),
    })
    if (!res.ok) {
      alert('关联参会人员失败')
      return
    }

    setMessages((items) => items.map((item) => (
      getSpeakerIdentity(item) === identityId
        ? { ...item, speaker_identity_id: identityId, speaker_name: name, role: 'customer', need_reply: true, corrected: true }
        : item
    )))
  }

  async function correctMessageSpeaker(messageId: string, participantId: string) {
    if (!sessionId) return
    const body = participantId
      ? { participant_id: participantId }
      : { speaker_name: '未知说话人', role: 'unknown' }
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages/${messageId}/speaker`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      alert('修正说话人失败')
      return
    }
    const updated: Message = await res.json()
    setMessages((items) => items.map((item) => (item.id === updated.id ? updated : item)))
    if (updated.ai_suggestion) setLatestSuggestion(updated.ai_suggestion)
  }

  async function summarizeSession() {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/meetings/${sessionId}/summary`, { method: 'POST' })
    if (!res.ok) {
      const error = await res.json().catch(() => null)
      alert(error?.detail || '生成会议总结失败')
      return
    }
    const data = await res.json()
    setSummary(data.summary)
    await loadSessions()
  }

  async function exportSession() {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/meetings/${sessionId}/export`, { method: 'POST' })
    const data = await res.json()
    alert(`已导出：${data.file}`)
  }

  function updateConfig<K extends keyof ModelConfig>(key: K, value: ModelConfig[K]) {
    setConfig((current) => ({ ...current, [key]: value }))
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>AI 会谈辅助</strong>
          <span>Meeting Copilot</span>
        </div>
        <nav className="main-menu">
          <button className={page === 'new' ? 'active' : ''} onClick={() => setPage('new')}>新建会议</button>
          <button className={page === 'history' ? 'active' : ''} onClick={() => { setPage('history'); void loadSessions() }}>历史会议</button>
          <button className={page === 'settings' ? 'active' : ''} onClick={() => setPage('settings')}>系统设置</button>
        </nav>
        {sessionId && (
          <button className={page === 'room' ? 'active room-entry' : 'room-entry'} onClick={() => setPage('room')}>
            返回会议室
          </button>
        )}
      </aside>

      <main className="content">
        {page === 'new' && renderNewMeeting()}
        {page === 'history' && renderHistory()}
        {page === 'settings' && renderSettings()}
        {page === 'room' && renderMeetingRoom()}
      </main>
    </div>
  )

  function renderNewMeeting() {
    return (
      <section className="page-card narrow-card">
        <div className="page-title">
          <h1>新建会议</h1>
          <p>只需填写客户名称和会晤目标，会议时间戳由系统后台自动记录。</p>
        </div>
        <label className="field">
          客户名称
          <input placeholder="例如：上海某某科技有限公司" value={customerName} onChange={(e) => setCustomerName(e.target.value)} />
        </label>
        <label className="field">
          会晤目标
          <textarea value={goal} onChange={(e) => setGoal(e.target.value)} />
        </label>
        <button className="primary-action" onClick={enterMeeting}>进入会议</button>
      </section>
    )
  }

  function renderHistory() {
    return (
      <section className="page-card">
        <div className="page-title row-between">
          <div>
            <h1>历史会议</h1>
            <p>查看本地保存的会议记录，并可重新进入会议室查看或继续导出。</p>
          </div>
          <button onClick={loadSessions}>刷新</button>
        </div>
        <div className="history-list">
          {sessions.length === 0 && <div className="empty">暂无历史会议</div>}
          {sessions.map((session) => (
            <button className="history-item" key={session.id} onClick={() => openSession(session.id)}>
              <strong>{session.title}</strong>
              <span>{session.goal || '未填写会晤目标'}</span>
              <small>{session.started_at} · {session.message_count} 条记录 · {session.has_summary ? '已总结' : '未总结'}</small>
            </button>
          ))}
        </div>
      </section>
    )
  }

  function renderSettings() {
    return (
      <div className="settings-stack">
        <section className="page-card">
          <div className="page-title">
            <h1>模型配置</h1>
            <p>配置 LLM、Whisper、声纹阈值和前端能量切分参数。</p>
          </div>
          <div className="config-grid">
            <label>LLM Provider<input value={config.llm_provider} onChange={(e) => updateConfig('llm_provider', e.target.value)} /></label>
            <label>LLM Model<input value={config.llm_model} onChange={(e) => updateConfig('llm_model', e.target.value)} /></label>
            <label>Base URL<input value={config.llm_base_url} onChange={(e) => updateConfig('llm_base_url', e.target.value)} /></label>
            <label>API Key<input type="password" value={config.llm_api_key} onChange={(e) => updateConfig('llm_api_key', e.target.value)} /></label>
            <label>Whisper Model<input value={config.whisper_model} onChange={(e) => updateConfig('whisper_model', e.target.value)} /></label>
            <label>Whisper Device<input value={config.whisper_device} onChange={(e) => updateConfig('whisper_device', e.target.value)} /></label>
            <label>声纹阈值<input type="number" step="0.01" value={config.speaker_threshold} onChange={(e) => updateConfig('speaker_threshold', Number(e.target.value))} /></label>
            <label>能量阈值<input type="number" step="0.001" value={config.energy_threshold} onChange={(e) => updateConfig('energy_threshold', Number(e.target.value))} /></label>
            <label>静音切分 ms<input type="number" value={config.silence_duration_ms} onChange={(e) => updateConfig('silence_duration_ms', Number(e.target.value))} /></label>
            <label>最短语音 ms<input type="number" value={config.min_speech_duration_ms} onChange={(e) => updateConfig('min_speech_duration_ms', Number(e.target.value))} /></label>
          </div>
          <button onClick={saveConfig}>保存模型配置</button>
        </section>

        <section className="page-card">
          <div className="page-title">
            <h1>系统主题风格</h1>
            <p>切换本地页面的显示风格，不影响后端数据。</p>
          </div>
          <div className="theme-options">
            <button className={theme === 'dark' ? 'active' : ''} onClick={() => setTheme('dark')}>深色商务</button>
            <button className={theme === 'light' ? 'active' : ''} onClick={() => setTheme('light')}>浅色简洁</button>
            <button className={theme === 'blue' ? 'active' : ''} onClick={() => setTheme('blue')}>蓝色科技</button>
          </div>
        </section>
      </div>
    )
  }

  function renderMeetingRoom() {
    return (
      <div className="meeting-room">
        <section className="page-card room-header">
          <div>
            <h1>{sessionTitle || '会议室'}</h1>
            <p className="muted">当前会话：{sessionId || '-'}</p>
          </div>
          <div className="room-actions">
            {!recording ? <button onClick={startRecording}>开始录音</button> : <button className="danger" onClick={stopRecording}>停止录音</button>}
            <button onClick={exportSession}>导出会议</button>
          </div>
        </section>

        <section className="page-card speaker-panel">
          <div className="section-heading">
            <h2>参会人员</h2>
          </div>
          <div className="speaker-list">
            {recognizedSpeakers.length === 0 && <div className="empty">开始录音后，系统会在这里动态添加识别到的个体 ID。</div>}
            {recognizedSpeakers.map((speaker) => (
              <div className="speaker-row" key={speaker.id}>
                <code>{speaker.id}</code>
                <input
                  placeholder="输入参会人员名称并回车关联"
                  value={speakerNames[speaker.id] ?? speaker.name}
                  onChange={(e) => setSpeakerNames((current) => ({ ...current, [speaker.id]: e.target.value }))}
                  onBlur={() => applySpeakerName(speaker.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void applySpeakerName(speaker.id)
                  }}
                />
                <span>{speaker.count} 条发言</span>
                <span>匹配分：{speaker.latestScore?.toFixed(2) ?? '-'}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="room-columns">
          <section className="page-card conversation-card">
            <div className="section-heading">
              <h2>实时会话</h2>
              <span>当前能量：{energyLevel.toFixed(4)} / 阈值：{config.energy_threshold}</span>
            </div>
            <div className="messages">
              {messages.length === 0 && <div className="empty">暂无会话内容</div>}
              {messages.map((message) => (
                <div className={`message ${message.role}`} key={message.id}>
                  <div className="message-header">
                    <strong>{message.speaker_name}{message.corrected ? '（已修正）' : ''}</strong>
                    <code>{getSpeakerIdentity(message)}</code>
                    <span className="score">匹配分：{message.speaker_score?.toFixed(2) ?? '-'}</span>
                    <select value={message.participant_id ?? ''} onChange={(e) => correctMessageSpeaker(message.id, e.target.value)}>
                      <option value="">手动选择已建声纹</option>
                      {participants.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                  <p>{message.text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="page-card ai-card">
            <h2>AI 回复</h2>
            <p>{latestSuggestion || '当客户或需要答复的参会人发言后，这里会显示建议回复。'}</p>
            <div className="suggestion-history">
              {messages.filter((message) => message.ai_suggestion).map((message) => (
                <blockquote key={message.id}>{message.ai_suggestion}</blockquote>
              ))}
            </div>
          </section>
        </div>

        <section className="page-card summary-card">
          <div className="section-heading">
            <h2>会议总结</h2>
            <button onClick={summarizeSession}>生成会议总结</button>
          </div>
          <p>{summary || '会议总结默认不自动生成。请在会议结束后人工点击按钮触发。'}</p>
        </section>
      </div>
    )
  }
}
