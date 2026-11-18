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
  llm_api_type: 'chat_completions' | 'responses'
  llm_timeout_seconds: number
  model_availability: Record<string, boolean>
  custom_models: CustomModelConfig[]
  whisper_model: string
  whisper_device: string
  whisper_compute_type: string
  speaker_threshold: number
  energy_threshold: number
  silence_duration_ms: number
  min_speech_duration_ms: number
}

interface CustomModelConfig {
  id: string
  name: string
  model: string
  base_url: string
  api_type: 'chat_completions' | 'responses'
  description: string
}

interface ModelPreset {
  id: string
  name: string
  model: string
  baseUrl: string
  apiType: 'chat_completions' | 'responses'
  description: string
  custom?: boolean
}

interface RecognizedSpeaker {
  id: string
  name: string
  role: Role
  count: number
  latestScore?: number
}

interface AiQaItem {
  id: string
  speakerName: string
  question: string
  answer: string
  status: 'thinking' | 'done' | 'error'
}

interface AgentDecision {
  id: string
  type: string
  reason: string
  content: string
  message_id?: string | null
  speaker_name: string
  created_at: string
}

interface AgentMemory {
  meeting_id: string
  goal: string
  short_term_context: string[]
  pain_points: string[]
  risks: string[]
  commitments: string[]
  todos: string[]
  questions: string[]
  decisions: AgentDecision[]
  updated_at: string
}

const defaultConfig: ModelConfig = {
  llm_provider: 'deepseek',
  llm_model: 'deepseek-chat',
  llm_base_url: 'https://api.deepseek.com',
  llm_api_key: '',
  llm_api_type: 'chat_completions',
  llm_timeout_seconds: 30,
  model_availability: {
    deepseek: true,
    gpt: false,
    qwen: false,
    grok: false,
  },
  custom_models: [],
  whisper_model: 'small',
  whisper_device: 'cpu',
  whisper_compute_type: 'int8',
  speaker_threshold: 0.7,
  energy_threshold: 0.02,
  silence_duration_ms: 800,
  min_speech_duration_ms: 1000,
}

const modelPresets: ModelPreset[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    model: 'deepseek-chat',
    baseUrl: 'https://api.deepseek.com',
    apiType: 'chat_completions' as const,
    description: '适合中文商务会谈，成本较低。',
  },
  {
    id: 'gpt',
    name: 'GPT / OpenAI',
    model: 'gpt-4o-mini',
    baseUrl: 'https://api.openai.com',
    apiType: 'responses' as const,
    description: 'OpenAI Compatible 官方接口。',
  },
  {
    id: 'qwen',
    name: 'Qwen / 通义千问',
    model: 'qwen-plus',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode',
    apiType: 'chat_completions' as const,
    description: '阿里云 DashScope OpenAI 兼容模式。',
  },
  {
    id: 'grok',
    name: 'Grok / xAI',
    model: 'grok-3-mini',
    baseUrl: 'https://api.x.ai',
    apiType: 'responses' as const,
    description: 'xAI OpenAI Compatible 接口。',
  },
]

function AgentMemoryBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="agent-memory-block">
      <h3>{title}</h3>
      {items.length === 0 && <p className="empty">暂无</p>}
      {items.map((item, index) => <p key={`${title}_${index}`}>{item}</p>)}
    </div>
  )
}

export function App() {
  const [page, setPage] = useState<Page>('new')
  const [theme, setTheme] = useState<Theme>('dark')
  const [customerName, setCustomerName] = useState('')
  const [goal, setGoal] = useState('了解客户当前业务痛点，并推动下一次需求调研。')
  const [sessionId, setSessionId] = useState<string>('')
  const [sessionTitle, setSessionTitle] = useState('')
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({})
  const [speakerPushTargets, setSpeakerPushTargets] = useState<Record<string, boolean>>({})
  const [aiQas, setAiQas] = useState<AiQaItem[]>([])
  const [agentMemory, setAgentMemory] = useState<AgentMemory | null>(null)
  const [latestSuggestion, setLatestSuggestion] = useState('')
  const [summary, setSummary] = useState('')
  const [recording, setRecording] = useState(false)
  const [speakerPanelOpen, setSpeakerPanelOpen] = useState(true)
  const [energyLevel, setEnergyLevel] = useState(0)
  const [config, setConfig] = useState<ModelConfig>(defaultConfig)
  const [connectionTest, setConnectionTest] = useState('')
  const [testingConnection, setTestingConnection] = useState(false)

  const mediaStreamRef = useRef<MediaStream | null>(null)
  const segmentRecorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const recordingRef = useRef(false)
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

  const availableModelCards: ModelPreset[] = useMemo(() => [
    ...modelPresets,
    ...(config.custom_models || []).map((item) => ({
      id: item.id,
      name: item.name,
      model: item.model,
      baseUrl: item.base_url,
      apiType: item.api_type,
      description: item.description || '用户自定义模型',
      custom: true,
    })),
  ], [config.custom_models])

  function getSpeakerIdentity(message: Message) {
    return message.speaker_identity_id || message.participant_id || `voice_${message.id}`
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
    const configToSave = ensureCurrentModelVisible(config)
    const res = await fetch(`${API_BASE}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configToSave),
    })
    if (!res.ok) {
      alert('模型配置保存失败')
      return
    }
    setConfig(await res.json())
    alert('模型配置已保存')
  }

  async function testModelConnection() {
    setTestingConnection(true)
    setConnectionTest('正在测试当前模型连接...')
    try {
      const res = await fetch(`${API_BASE}/api/config/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      const data = await res.json()
      setConnectionTest(`${data.ok ? '✅ 连接成功' : '❌ 连接失败'}｜${data.provider} / ${data.model}｜${data.latency_ms}ms｜${data.message}`)
    } catch (error) {
      setConnectionTest(`❌ 连接测试异常：${String(error)}`)
    } finally {
      setTestingConnection(false)
    }
  }

  function applyModelPreset(presetId: string) {
    const preset = availableModelCards.find((item) => item.id === presetId)
    if (!preset) return
    setConfig((current) => ({
      ...current,
      llm_provider: preset.id,
      llm_model: preset.model,
      llm_base_url: preset.baseUrl,
      llm_api_type: preset.apiType,
      model_availability: {
        ...current.model_availability,
        [preset.id]: true,
      },
    }))
    setConnectionTest('')
  }

  function toggleModelAvailability(presetId: string, enabled: boolean) {
    setConfig((current) => ({
      ...current,
      model_availability: {
        ...current.model_availability,
        [presetId]: enabled,
      },
    }))
  }

  function normalizeModelId(value: string) {
    return value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '')
  }

  function ensureCurrentModelVisible(current: ModelConfig): ModelConfig {
    const providerId = normalizeModelId(current.llm_provider || current.llm_model)
    if (!providerId || !current.llm_model.trim() || !current.llm_base_url.trim()) {
      return current
    }

    const presetExists = modelPresets.some((item) => item.id === providerId)
    const nextAvailability = {
      ...current.model_availability,
      [providerId]: true,
    }

    if (presetExists) {
      return {
        ...current,
        llm_provider: providerId,
        model_availability: nextAvailability,
      }
    }

    const nextCustomModel: CustomModelConfig = {
      id: providerId,
      name: current.llm_provider.trim() || providerId,
      model: current.llm_model.trim(),
      base_url: current.llm_base_url.trim().replace(/\/$/, ''),
      api_type: current.llm_api_type,
      description: `保存的模型配置：${current.llm_model.trim()}`,
    }

    const existingIndex = (current.custom_models || []).findIndex((item) => item.id === providerId)
    const nextCustomModels = [...(current.custom_models || [])]
    if (existingIndex >= 0) {
      nextCustomModels[existingIndex] = nextCustomModel
    } else {
      nextCustomModels.push(nextCustomModel)
    }

    return {
      ...current,
      llm_provider: providerId,
      llm_base_url: nextCustomModel.base_url,
      model_availability: nextAvailability,
      custom_models: nextCustomModels,
    }
  }

  function removeCustomModel(id: string) {
    setConfig((current) => {
      const nextAvailability = { ...current.model_availability }
      delete nextAvailability[id]
      const removingActive = current.llm_provider === id
      return {
        ...current,
        llm_provider: removingActive ? defaultConfig.llm_provider : current.llm_provider,
        llm_model: removingActive ? defaultConfig.llm_model : current.llm_model,
        llm_base_url: removingActive ? defaultConfig.llm_base_url : current.llm_base_url,
        llm_api_type: removingActive ? defaultConfig.llm_api_type : current.llm_api_type,
        model_availability: nextAvailability,
        custom_models: (current.custom_models || []).filter((item) => item.id !== id),
      }
    })
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
    setSpeakerPushTargets({})
    setAiQas([])
    setAgentMemory(null)
    setLatestSuggestion('')
    setSummary('')
    setPage('room')
    await loadSessions()
    await loadAgentMemory(data.id)
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
    setAiQas((data.messages || []).filter((m) => m.ai_suggestion).map((m) => ({
      id: m.id,
      speakerName: m.speaker_name,
      question: m.text,
      answer: m.ai_suggestion || '',
      status: 'done',
    })))
    setLatestSuggestion([...data.messages].reverse().find((m) => m.ai_suggestion)?.ai_suggestion || '')
    setSpeakerNames({})
    setSpeakerPushTargets({})
    setPage('room')
    await loadAgentMemory(data.id)
  }

  async function startRecording() {
    if (!sessionId) {
      alert('请先新建会议并进入会议室')
      return
    }

    activeSessionIdRef.current = sessionId
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (error) {
      console.error(error)
      alert('无法访问麦克风，请检查浏览器麦克风权限。')
      return
    }
    const audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)

    audioContextRef.current = audioContext
    analyserRef.current = analyser
    mediaStreamRef.current = stream
    chunksRef.current = []
    recordingRef.current = true
    speechActiveRef.current = false

    setRecording(true)
    monitorEnergy()
  }

  function startSpeechSegment() {
    const stream = mediaStreamRef.current
    if (!stream || segmentRecorderRef.current) return

    chunksRef.current = []
    speechActiveRef.current = true
    segmentStartedAtRef.current = Date.now()
    lastVoiceAtRef.current = Date.now()

    const recorder = new MediaRecorder(stream)
    segmentRecorderRef.current = recorder

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data)
    }

    recorder.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
      chunksRef.current = []
      segmentRecorderRef.current = null
      speechActiveRef.current = false
      if (blob.size > 0) await uploadAudioSegment(blob)
    }

    recorder.start(250)
  }

  function monitorEnergy() {
    const analyser = analyserRef.current
    if (!analyser || !recordingRef.current) return

    const buffer = new Float32Array(analyser.fftSize)
    analyser.getFloatTimeDomainData(buffer)
    const rms = Math.sqrt(buffer.reduce((sum, value) => sum + value * value, 0) / buffer.length)
    const now = Date.now()
    const activeConfig = configRef.current

    setEnergyLevel(rms)

    if (rms >= activeConfig.energy_threshold) {
      lastVoiceAtRef.current = now
      if (!speechActiveRef.current) {
        startSpeechSegment()
      }
    }

    if (speechActiveRef.current) {
      const silenceMs = now - lastVoiceAtRef.current
      const speechMs = now - segmentStartedAtRef.current
      if (silenceMs >= activeConfig.silence_duration_ms && speechMs >= activeConfig.min_speech_duration_ms) {
        flushSpeechSegment()
      }
    }

    animationFrameRef.current = requestAnimationFrame(monitorEnergy)
  }

  function flushSpeechSegment() {
    const recorder = segmentRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    } else {
      speechActiveRef.current = false
      chunksRef.current = []
      segmentRecorderRef.current = null
    }
  }

  async function uploadAudioSegment(blob: Blob) {
    const activeSessionId = activeSessionIdRef.current || sessionId
    if (!activeSessionId) return

    const form = new FormData()
    form.append('session_id', activeSessionId)
    form.append('file', blob, 'speech.webm')
    try {
      const res = await fetch(`${API_BASE}/api/meetings/${activeSessionId}/audio`, { method: 'POST', body: form })
      if (!res.ok) {
        const error = await res.json().catch(() => null)
        alert(error?.detail || '音频识别失败，请稍后重试。')
        return
      }
      const message: Message = await res.json()
      setMessages((items) => [...items, message])
      if (message.ai_suggestion) setLatestSuggestion(message.ai_suggestion)
      void maybePushQuestionToAi(message, [...messages, message])
      await loadSessions()
      await loadAgentMemory(activeSessionId)
    } catch (error) {
      console.error(error)
    }
  }

  function stopRecording() {
    recordingRef.current = false
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
    flushSpeechSegment()
    window.setTimeout(() => {
      void audioContextRef.current?.close()
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
      mediaStreamRef.current = null
      analyserRef.current = null
      audioContextRef.current = null
      setEnergyLevel(0)
    }, 300)
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
    await loadAgentMemory(sessionId)
  }

  async function loadAgentMemory(meetingId = sessionId) {
    if (!meetingId) return
    const res = await fetch(`${API_BASE}/api/meetings/${meetingId}/agent/memory`)
    if (res.ok) setAgentMemory(await res.json())
  }

  async function runAgent() {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/meetings/${sessionId}/agent/run`, { method: 'POST' })
    if (!res.ok) {
      alert('Agent 运行失败')
      return
    }
    const data = await res.json()
    setAgentMemory(data.memory)
  }

  function toggleSpeakerAiPush(identityId: string, enabled: boolean) {
    setSpeakerPushTargets((current) => ({ ...current, [identityId]: enabled }))
  }

  function isLikelyQuestion(text: string) {
    const value = text.trim()
    if (!value) return false
    if (/[?？]$/.test(value) || /[?？]/.test(value)) return true
    return /(吗|呢|什么|为什么|为何|怎么|如何|是否|能否|能不能|可不可以|有没有|哪[个些里]|多少|几|何时|什么时候|请问)/.test(value)
  }

  async function maybePushQuestionToAi(message: Message, historyMessages: Message[]) {
    const identityId = getSpeakerIdentity(message)
    if (!speakerPushTargets[identityId]) return
    if (!isLikelyQuestion(message.text)) return

    const qaId = `qa_${message.id}`
    const speakerName = speakerNames[identityId] || message.speaker_name || identityId
    setAiQas((items) => [...items, {
      id: qaId,
      speakerName,
      question: message.text,
      answer: 'AI 正在思考...',
      status: 'thinking',
    }])

    const conversationHistory = historyMessages
      .slice(-8)
      .map((item) => `${item.speaker_name}: ${item.text}`)
      .join('\n')

    try {
      const res = await fetch(`${API_BASE}/api/ai/suggest-reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meeting_goal: goal,
          conversation_history: conversationHistory,
          latest_customer_message: message.text,
        }),
      })
      if (!res.ok) {
        const error = await res.json().catch(() => null)
        throw new Error(error?.detail || 'AI 回复生成失败')
      }
      const data = await res.json()
      setLatestSuggestion(data.suggestion)
      setAiQas((items) => items.map((item) => item.id === qaId ? {
        ...item,
        answer: data.suggestion,
        status: 'done',
      } : item))
    } catch (error) {
      setAiQas((items) => items.map((item) => item.id === qaId ? {
        ...item,
        answer: `生成失败：${String(error)}`,
        status: 'error',
      } : item))
    }
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
            <p>管理 Grok、Qwen、GPT 等模型可用性，测试连接，并配置当前会议助手使用的模型。</p>
          </div>

          <div className="model-section-title">
            <h2>模型可用性</h2>
            <span>启用后表示该模型可被系统选择；点击“套用”会将其设为当前 LLM。</span>
          </div>
          <div className="model-provider-grid">
            {availableModelCards.map((preset) => {
              const enabled = config.model_availability?.[preset.id] ?? false
              const active = config.llm_provider === preset.id
              return (
                <div className={active ? 'model-card active' : 'model-card'} key={preset.id}>
                  <div className="model-card-header">
                    <div>
                      <strong>{preset.name}</strong>
                      <small>{preset.model}</small>
                    </div>
                    <label className="switch-label">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={(e) => toggleModelAvailability(preset.id, e.target.checked)}
                      />
                      可用
                    </label>
                  </div>
                  <p>{preset.description}</p>
                  <code>{preset.baseUrl}</code>
                  <div className="model-card-actions">
                    <button className="secondary-action" onClick={() => applyModelPreset(preset.id)}>套用</button>
                    {preset.custom && <button className="danger subtle-danger" onClick={() => removeCustomModel(preset.id)}>删除</button>}
                  </div>
                </div>
              )
            })}
          </div>

          <div className="model-section-title">
            <h2>当前 LLM 连接</h2>
            <span>保存后，当前 Provider/Model/Base URL 会自动显示在“模型可用性”区域。</span>
          </div>
          <div className="config-grid">
            <label>LLM Provider<input value={config.llm_provider} onChange={(e) => updateConfig('llm_provider', e.target.value)} /></label>
            <label>LLM Model<input value={config.llm_model} onChange={(e) => updateConfig('llm_model', e.target.value)} /></label>
            <label>Base URL<input value={config.llm_base_url} onChange={(e) => updateConfig('llm_base_url', e.target.value)} /></label>
            <label>接口类型
              <select value={config.llm_api_type} onChange={(e) => updateConfig('llm_api_type', e.target.value as ModelConfig['llm_api_type'])}>
                <option value="chat_completions">Chat Completions (/v1/chat/completions)</option>
                <option value="responses">Responses (/v1/responses)</option>
              </select>
            </label>
            <label>API Key<input type="password" value={config.llm_api_key} onChange={(e) => updateConfig('llm_api_key', e.target.value)} /></label>
            <label>请求超时秒数<input type="number" value={config.llm_timeout_seconds} onChange={(e) => updateConfig('llm_timeout_seconds', Number(e.target.value))} /></label>
          </div>

          <div className="model-actions">
            <button onClick={saveConfig}>保存模型配置</button>
            <button className="secondary-action" disabled={testingConnection} onClick={testModelConnection}>
              {testingConnection ? '测试中...' : '测试连接'}
            </button>
          </div>
          {connectionTest && <div className="connection-result">{connectionTest}</div>}

          <div className="model-section-title">
            <h2>本地语音与识别参数</h2>
            <span>控制 Whisper、声纹匹配和浏览器能量切分。</span>
          </div>
          <div className="config-grid">
            <label>Whisper Model<input value={config.whisper_model} onChange={(e) => updateConfig('whisper_model', e.target.value)} /></label>
            <label>Whisper Device<input value={config.whisper_device} onChange={(e) => updateConfig('whisper_device', e.target.value)} /></label>
            <label>Whisper Compute Type<input value={config.whisper_compute_type} onChange={(e) => updateConfig('whisper_compute_type', e.target.value)} /></label>
            <label>声纹阈值<input type="number" step="0.01" value={config.speaker_threshold} onChange={(e) => updateConfig('speaker_threshold', Number(e.target.value))} /></label>
            <label>能量阈值<input type="number" step="0.001" value={config.energy_threshold} onChange={(e) => updateConfig('energy_threshold', Number(e.target.value))} /></label>
            <label>静音切分 ms<input type="number" value={config.silence_duration_ms} onChange={(e) => updateConfig('silence_duration_ms', Number(e.target.value))} /></label>
            <label>最短语音 ms<input type="number" value={config.min_speech_duration_ms} onChange={(e) => updateConfig('min_speech_duration_ms', Number(e.target.value))} /></label>
          </div>
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
            <button className="secondary-action" onClick={() => setSpeakerPanelOpen((open) => !open)}>
              {speakerPanelOpen ? '折叠' : '展开'}
            </button>
          </div>
          {speakerPanelOpen && (
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
                  <label className="speaker-push-toggle">
                    <input
                      type="checkbox"
                      checked={speakerPushTargets[speaker.id] ?? false}
                      onChange={(e) => toggleSpeakerAiPush(speaker.id, e.target.checked)}
                    />
                    推送 AI
                  </label>
                  <span>{speaker.count} 条发言</span>
                  <span>匹配分：{speaker.latestScore?.toFixed(2) ?? '-'}</span>
                </div>
              ))}
            </div>
          )}
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
                  </div>
                  <p>{message.text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="page-card ai-card">
            <h2>AI 回复</h2>
            <div className="qa-panel">
              {aiQas.length === 0 && (
                <div className="empty qa-empty">
                  勾选“参会人员”中的“推送 AI”后，该参会人的问题会自动进入这里生成回复。
                </div>
              )}
              {aiQas.map((item) => (
                <div className={`qa-item ${item.status}`} key={item.id}>
                  <div className="qa-question">
                    <span>{item.speakerName}</span>
                    <p>{item.question}</p>
                  </div>
                  <div className="qa-answer">
                    <span>AI 回复</span>
                    <p>{item.answer}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="page-card agent-card">
          <div className="section-heading">
            <h2>Agent 工作台</h2>
            <button className="secondary-action" onClick={runAgent}>刷新 Agent 记忆</button>
          </div>
          {!agentMemory ? (
            <div className="empty">暂无 Agent 记忆。录音产生会话后，Agent 会自动维护上下文。</div>
          ) : (
            <div className="agent-grid">
              <AgentMemoryBlock title="短期上下文" items={agentMemory.short_term_context} />
              <AgentMemoryBlock title="客户痛点" items={agentMemory.pain_points} />
              <AgentMemoryBlock title="风险/异议" items={agentMemory.risks} />
              <AgentMemoryBlock title="承诺事项" items={agentMemory.commitments} />
              <AgentMemoryBlock title="后续待办" items={agentMemory.todos} />
              <AgentMemoryBlock title="关键问题" items={agentMemory.questions} />
              <div className="agent-memory-block decisions-block">
                <h3>决策日志</h3>
                {agentMemory.decisions.length === 0 && <p className="empty">暂无决策日志</p>}
                {agentMemory.decisions.slice(-8).reverse().map((decision) => (
                  <div className="decision-item" key={decision.id}>
                    <strong>{decision.type}</strong>
                    <span>{decision.reason}</span>
                    <p>{decision.speaker_name}: {decision.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

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
