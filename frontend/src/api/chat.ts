import type { CreateSessionResponse, SessionMessages, Topic } from './student'

export const CHAT_API_ENABLED = import.meta.env.VITE_CHAT_API_ENABLED === 'true'
const base = (import.meta.env.VITE_CHAT_API_URL || 'http://127.0.0.1:8008').replace(/\/$/, '')
const prefix = 'pr205-chat-only:v1:' + base + ':'
interface SavedSession {
  session_id: string
  topic_id: string
  session_token: string
  pending?: { content: string; request_id: string }
}
class ChatApiError extends Error {
  isAxiosError = true
  response: { status: number; data: unknown }
  constructor(status: number, data: unknown) {
    super('Chat API failed')
    this.response = { status, data }
  }
}
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(base + '/chat-api/v1' + path, options)
  } catch {
    throw new ChatApiError(503, {
      detail: '無法連上 AI 對話服務，請確認根目錄的 npm run dev 仍在執行。',
    })
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new ChatApiError(res.status, body)
  return body as T
}
function savedForId(id: string): { key: string; value: SavedSession } {
  for (let index = 0; index < sessionStorage.length; index++) {
    const key = sessionStorage.key(index)
    if (!key?.startsWith(prefix)) continue
    const value = JSON.parse(sessionStorage.getItem(key) || 'null') as SavedSession | null
    if (value?.session_id === id) return { key, value }
  }
  throw new ChatApiError(404, { detail: '找不到這個分頁的對話，請回到課程後重新進入。' })
}
function headers(token: string) {
  return { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }
}

export const chatApi = {
  async createOrResume(topic: Topic, account: string): Promise<CreateSessionResponse> {
    const key = prefix + account + ':' + topic.topic_id
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null') as SavedSession | null
    if (saved) {
      try {
        await this.getMessages(saved.session_id)
        return saved
      } catch (error) {
        if (!(error instanceof ChatApiError) || ![403, 404].includes(error.response.status))
          throw error
        sessionStorage.removeItem(key)
      }
    }
    const session = await request<SavedSession>('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic_id: topic.topic_id,
        title: topic.title,
        description: topic.description,
        age_range: topic.age_range,
        max_rounds: topic.max_rounds,
      }),
    })
    sessionStorage.setItem(key, JSON.stringify(session))
    return session
  },
  getMessages(id: string) {
    const { value } = savedForId(id)
    return request<SessionMessages>('/sessions/' + encodeURIComponent(id) + '/messages', {
      headers: headers(value.session_token),
    })
  },
  prepareSend(id: string, content: string) {
    const { key, value } = savedForId(id)
    // A lost terminal event can be retried without another successful AI turn.
    const pending =
      value.pending?.content === content
        ? value.pending
        : { content, request_id: crypto.randomUUID() }
    value.pending = pending
    sessionStorage.setItem(key, JSON.stringify(value))
    return {
      url: base + '/chat-api/v1/sessions/' + encodeURIComponent(id) + '/messages/stream',
      headers: headers(value.session_token),
      body: JSON.stringify(pending),
    }
  },
  finishSend(id: string) {
    const { key, value } = savedForId(id)
    delete value.pending
    sessionStorage.setItem(key, JSON.stringify(value))
  },
}
