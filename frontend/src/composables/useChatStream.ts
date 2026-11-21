import { ref } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE_URL } from '@/api/client'

/** done 事件（docs/API功能規格.md v0.2「發送回答並串流接收 AI 回覆」） */
export interface StreamDone {
  message_id: string
  completed_turns: number
  is_completed: boolean
  /** AI 判斷可以結束了，等學生選「結束」或「繼續」 */
  awaiting_end_consent: boolean
}

/** 串流失敗時丟出的錯誤，格式模仿 axios，這樣 getApiErrorMessage 也能用 */
export class StreamError extends Error {
  isAxiosError = true
  response?: { status: number; data: unknown }
  constructor(status: number, data: unknown) {
    super(`Stream failed with status ${status}`)
    this.response = { status, data }
  }
}

/**
 * 蘇格拉底對話串流（SSE）。
 * 對應 API: POST /sessions/{sessionId}/messages/stream，送 { content, request_id }
 *
 * 瀏覽器原生的 EventSource 只支援 GET、也不能帶 Authorization header，
 * 這個 API 是 POST + 需要帶 token，所以用 @microsoft/fetch-event-source。
 *
 * 事件格式：
 *   data: 文字片段             ← 一般訊息，逐段接起來
 *   event: done / data: {…}   ← 最後一個，帶 StreamDone（已用回合數、是否結束、是否詢問結束）
 *
 * request_id：同一則回答重試時要沿用同一個，後端才不會重複扣回合。
 */
export function useChatStream() {
  const isStreaming = ref(false)

  async function streamMessage(
    sessionId: string,
    content: string,
    requestId: string,
    handlers: { onChunk: (chunk: string) => void; onDone?: (done: StreamDone) => void },
  ) {
    isStreaming.value = true
    const token = localStorage.getItem('access_token')
    const controller = new AbortController()

    try {
      await fetchEventSource(
        `${API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}/messages/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: token ? `Bearer ${token}` : '',
          },
          body: JSON.stringify({ content, request_id: requestId }),
          signal: controller.signal,
          openWhenHidden: true,
          async onopen(response) {
            if (response.ok) return
            const data = await response.json().catch(() => ({}))
            throw new StreamError(response.status, data)
          },
          onmessage(event) {
            if (event.event === 'done') {
              handlers.onDone?.(JSON.parse(event.data) as StreamDone)
              controller.abort()
              return
            }
            handlers.onChunk(event.data)
          },
          onerror(err) {
            // 丟出錯誤讓 fetchEventSource 停止自動重試，由呼叫端處理
            throw err
          },
        },
      )
    } catch (err) {
      if (controller.signal.aborted) return
      throw err
    } finally {
      isStreaming.value = false
    }
  }

  return { isStreaming, streamMessage }
}
