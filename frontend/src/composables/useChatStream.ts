import { ref } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE_URL } from '@/api/client'

/**
 * 蘇格拉底對話串流(SSE)。
 * 對應 API: POST /student/sessions/{sessionId}/messages/stream
 *
 * 瀏覽器原生的 EventSource 只支援 GET、也不能帶 Authorization header,
 * 這個 API 是 POST + 需要帶 token,所以用 @microsoft/fetch-event-source。
 */
export function useChatStream() {
  const isStreaming = ref(false)

  async function streamMessage(
    sessionId: string,
    content: string,
    onChunk: (chunk: string) => void,
  ) {
    isStreaming.value = true
    const token = localStorage.getItem('access_token')

    try {
      await fetchEventSource(`${API_BASE_URL}/student/sessions/${sessionId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify({ content }),
        openWhenHidden: true,
        onmessage(event) {
          onChunk(event.data)
        },
        onerror(err) {
          // 拋出錯誤讓 fetchEventSource 停止自動重試,由呼叫端的 try/catch 處理。
          throw err
        },
      })
    } finally {
      isStreaming.value = false
    }
  }

  return { isStreaming, streamMessage }
}
