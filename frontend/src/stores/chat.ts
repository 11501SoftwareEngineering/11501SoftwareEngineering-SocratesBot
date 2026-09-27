import { ref } from 'vue'
import { defineStore } from 'pinia'
import { studentApi } from '@/api/student'
import { useChatStream } from '@/composables/useChatStream'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
}

/**
 * 單一對話 Session 的狀態(訊息列表、串流中狀態)。
 * 對應規格:建立/進入對話 Session、蘇格拉底對話發送與串流回覆(SSE)。
 */
export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isSending = ref(false)

  const { streamMessage } = useChatStream()

  async function startSession(topicId: string) {
    const res = await studentApi.createSession(topicId)
    sessionId.value = res.data.session_id
    messages.value = []
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim()
    if (!trimmed || !sessionId.value || isSending.value) return

    messages.value.push({ id: crypto.randomUUID(), role: 'user', text: trimmed })

    // 先放一個空的助教訊息,串流回來的文字片段直接往這個物件的 text 上疊加,
    // 畫面就會有逐字顯示的效果。
    const assistantMessage: ChatMessage = { id: crypto.randomUUID(), role: 'assistant', text: '' }
    messages.value.push(assistantMessage)

    isSending.value = true
    try {
      await streamMessage(sessionId.value, trimmed, (chunk) => {
        assistantMessage.text += chunk
      })
    } finally {
      isSending.value = false
    }
  }

  return { sessionId, messages, isSending, startSession, sendMessage }
})
