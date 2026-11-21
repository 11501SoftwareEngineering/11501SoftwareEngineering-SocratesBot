import { ref } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE_URL, apiClient } from '@/api/client'
import type { DialogueStatus, LifecycleFields } from '@/api/sessions'

/** done 事件（docs/API功能規格.md v0.2「發送回答並串流接收 AI 回覆」） */
export interface StreamDone extends LifecycleFields {
  message_id: string
  completed_turns: number
  /** 只有 completed 才是 true；回合用完（ended）是 false，要看 session_status／report_eligible */
  is_completed: boolean
  /** AI 判斷達成目標了，等學生選「結束」或「繼續」 */
  awaiting_end_consent: boolean
  /** 這一回合結束後的對話狀態：回合用完時是 ended（舊後端沒有這個欄位） */
  session_status?: DialogueStatus
  goal_reached?: boolean
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
 *
 * 登入續期：這個請求不是走 axios，client.ts 的自動續期管不到。
 * access token 過期時後端回 401（還沒開始串流），這裡先打一次 GET /users/me 讓 axios 換新 token，
 * 再用同一個 request_id 重送一次；續期也失敗就照 axios 的流程登出（GET /users/me 的 401 會處理）。
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
    try {
      try {
        await openStream(sessionId, content, requestId, handlers)
      } catch (err) {
        if (!(err instanceof StreamError) || err.response?.status !== 401) throw err
        // token 過期：續期成功才重送，失敗就丟出原本的錯誤
        await apiClient.get('/users/me').catch(() => Promise.reject(err))
        await openStream(sessionId, content, requestId, handlers)
      }
    } finally {
      isStreaming.value = false
    }
  }

  return { isStreaming, streamMessage }
}

async function openStream(
  sessionId: string,
  content: string,
  requestId: string,
  handlers: { onChunk: (chunk: string) => void; onDone?: (done: StreamDone) => void },
) {
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
        // 跟 axios 一樣帶 cookie（refresh cookie）
        credentials: 'include',
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
  }
}
