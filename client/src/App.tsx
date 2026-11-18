import { useEffect, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

type Role = 'self' | 'customer' | 'other' | 'unknown'

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
  speaker_name: string
  role: Role
  text: string
  speaker_score?: number
  ai_suggestion?: string
}

export function App() {
  const [goal, setGoal] = useState('了解客户当前业务痛点，并推动下一次需求调研。')
  const [sessionId, setSessionId] = useState<string>('')
  const [participants, setParticipants] = useState<Participant[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [latestSuggestion, setLatestSuggestion] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<Role>('customer')
  const [needReply, setNeedReply] = useState(true)
  const [recording, setRecording] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)

  useEffect(() => {
    loadParticipants()
  }, [])

  async function loadParticipants() {
    const res = await fetch(`${API_BASE}/api/participants`)
    setParticipants(await res.json())
  }

  async function addParticipant() {
    if (!name.trim()) return
    await fetch(`${API_BASE}/api/participants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, role, need_reply: needReply }),
    })
    setName('')
    await loadParticipants()
  }

  async function createSession() {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '客户会谈', goal }),
    })
    const data = await res.json()
    setSessionId(data.id)
    setMessages([])
    setLatestSuggestion('')
  }

  async function uploadVoiceprint(participantId: string) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    const chunks: BlobPart[] = []

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' })
      const form = new FormData()
      form.append('file', blob, 'voiceprint.webm')
      await fetch(`${API_BASE}/api/participants/${participantId}/voiceprint`, {
        method: 'POST',
        body: form,
      })
      stream.getTracks().forEach((track) => track.stop())
      await loadParticipants()
      alert('声纹录入完成')
    }

    alert('开始录入声纹，请自然讲话 10 秒左右。')
    recorder.start()
    setTimeout(() => recorder.stop(), 10000)
  }

  async function startRecording() {
    const activeSessionId = sessionId || (await createSessionAndReturnId())
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = async (event) => {
      if (event.data.size <= 0) return
      const form = new FormData()
      form.append('session_id', activeSessionId)
      form.append('file', event.data, 'chunk.webm')
      try {
        const res = await fetch(`${API_BASE}/api/audio/process`, { method: 'POST', body: form })
        if (!res.ok) return
        const message: Message = await res.json()
        setMessages((items) => [...items, message])
        if (message.ai_suggestion) setLatestSuggestion(message.ai_suggestion)
      } catch (error) {
        console.error(error)
      }
    }

    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop())
    }

    recorder.start(6000)
    setRecording(true)
  }

  async function createSessionAndReturnId() {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '客户会谈', goal }),
    })
    const data = await res.json()
    setSessionId(data.id)
    setMessages([])
    return data.id
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }

  async function exportSession() {
    if (!sessionId) return
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/export`, { method: 'POST' })
    const data = await res.json()
    alert(`已导出：${data.file}`)
  }

  return (
    <div className="page">
      <header>
        <h1>AI 会谈辅助系统</h1>
        <p>本地语音识别 + 本地声纹识别 + 第三方大模型建议回复</p>
      </header>

      <section className="panel">
        <h2>会晤目标</h2>
        <textarea value={goal} onChange={(e) => setGoal(e.target.value)} />
        <button onClick={createSession}>新建会谈</button>
        {sessionId && <span className="session">当前会话：{sessionId}</span>}
      </section>

      <section className="panel">
        <h2>参会人</h2>
        <div className="row">
          <input placeholder="姓名" value={name} onChange={(e) => setName(e.target.value)} />
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="self">我方</option>
            <option value="customer">客户</option>
            <option value="other">其他</option>
          </select>
          <label>
            <input type="checkbox" checked={needReply} onChange={(e) => setNeedReply(e.target.checked)} />
            需要 AI 答复
          </label>
          <button onClick={addParticipant}>添加</button>
        </div>
        <div className="participants">
          {participants.map((p) => (
            <div className="participant" key={p.id}>
              <span>{p.name}</span>
              <span>{p.role}</span>
              <span>{p.need_reply ? '需要答复' : '无需答复'}</span>
              <span>{p.voiceprint_file ? '已录声纹' : '未录声纹'}</span>
              <button onClick={() => uploadVoiceprint(p.id)}>录入声纹</button>
            </div>
          ))}
        </div>
      </section>

      <main className="workspace">
        <section className="conversation">
          <h2>实时会话</h2>
          <div className="toolbar">
            {!recording ? <button onClick={startRecording}>开始录音</button> : <button onClick={stopRecording}>停止录音</button>}
            <button onClick={exportSession}>导出会话</button>
          </div>
          <div className="messages">
            {messages.map((m) => (
              <div className={`message ${m.role}`} key={m.id}>
                <strong>{m.speaker_name}</strong>
                <span className="score">匹配分：{m.speaker_score?.toFixed(2) ?? '-'}</span>
                <p>{m.text}</p>
              </div>
            ))}
          </div>
        </section>

        <aside className="suggestion">
          <h2>AI 建议回复</h2>
          <p>{latestSuggestion || '当客户或需要答复的参会人发言后，这里会显示建议回复。'}</p>
        </aside>
      </main>
    </div>
  )
}
