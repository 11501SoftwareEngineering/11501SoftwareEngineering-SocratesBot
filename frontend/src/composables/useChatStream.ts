import { onBeforeUnmount, ref } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE_URL } from '@/api/client'
import { CHAT_API_ENABLED, chatApi } from '@/api/chat'
import type { StreamDone } from '@/api/student'

export class StreamError extends Error {
  isAxiosError = true
  response: { status: number; data: unknown }
  constructor(status: number, data: unknown) {
    super('Chat stream failed')
    this.response = { status, data }
  }
}
export function useChatStream() {
  const isStreaming = ref(false)
  let active: AbortController | undefined
  onBeforeUnmount(() => active?.abort())
  async function streamMessage(
    sessionId: string,
    content: string,
    handlers: { onChunk: (chunk: string) => void; onDone?: (done: StreamDone) => void },
  ) {
    const token = localStorage.getItem('access_token')
    const target = CHAT_API_ENABLED
      ? chatApi.prepareSend(sessionId, content)
      : {
          url: `${API_BASE_URL}/student/sessions/${encodeURIComponent(sessionId)}/messages/stream`,
          headers: {
            'Content-Type': 'application/json',
            Authorization: token ? `Bearer ${token}` : '',
          },
          body: JSON.stringify({ content }),
        }
    const controller = new AbortController()
    active = controller
    isStreaming.value = true
    let finished = false
    try {
      await fetchEventSource(target.url, {
        method: 'POST',
        headers: target.headers,
        body: target.body,
        signal: controller.signal,
        openWhenHidden: true,
        async onopen(response) {
          if (response.ok && response.headers.get('content-type')?.includes('text/event-stream'))
            return
          throw new StreamError(response.status, await response.json().catch(() => ({})))
        },
        onmessage(event) {
          if (event.event === 'error') {
            const data = JSON.parse(event.data) as { status?: number; detail: string }
            throw new StreamError(data.status ?? 503, data)
          }
          if (event.event === 'done') {
            finished = true
            if (CHAT_API_ENABLED) chatApi.finishSend(sessionId)
            handlers.onDone?.(JSON.parse(event.data) as StreamDone)
            controller.abort()
            return
          }
          // PR205 mock sends raw text; real SSE uses JSON strings to preserve newlines.
          if (CHAT_API_ENABLED) {
            if (event.event === 'data') handlers.onChunk(JSON.parse(event.data) as string)
          } else handlers.onChunk(event.data)
        },
        onclose() {
          if (!finished)
            throw new StreamError(503, { detail: '連線中斷，請重新載入或重送相同訊息。' })
        },
        onerror(error) {
          throw error
        },
      })
      if (!finished) throw new StreamError(503, { detail: '這次連線已停止，請重新載入對話。' })
    } finally {
      if (active === controller) active = undefined
      isStreaming.value = false
    }
  }
  return { isStreaming, streamMessage }
}
