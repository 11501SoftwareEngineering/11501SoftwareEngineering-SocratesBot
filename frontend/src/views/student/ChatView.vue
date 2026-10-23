<script setup lang="ts">
/**
 * 學生：和導魷對話。對應 Figma「Student_Question」（node 171:280）。
 * API：POST /student/topics/{id}/sessions（建立或進入對話）
 *      ⚠️ GET /student/sessions/{id}/messages（拿歷史訊息，前端假設）
 *      POST /student/sessions/{id}/messages/stream（SSE 逐字回覆）
 *      POST /student/audio/transcribe（語音轉文字）
 * 回合數用完後對話結束，顯示「查看結果」。
 */
import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { studentApi, studentKeys, type ChatMessage } from '@/api/student'
import ChatBubble from '@/components/common/ChatBubble.vue'
import ChatInput from '@/components/common/ChatInput.vue'
import QueryState from '@/components/common/QueryState.vue'
import { Button } from '@/components/ui/button'
import { useChatStream } from '@/composables/useChatStream'
import { useStudentCourse } from '@/composables/useCourseDetail'
import { useVoiceRecorder } from '@/composables/useVoiceRecorder'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'

interface DisplayMessage extends ChatMessage {
  pending?: boolean
}

const route = useRoute()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const topicId = computed(() => String(route.params.topicId ?? ''))

const { data: course } = useStudentCourse(courseId)
const topic = computed(() => course.value?.topics.find((t) => t.topic_id === topicId.value))

// 1. 建立或進入對話（後端同一個學生同一題只會有一個 Session）
const sessionQuery = useQuery({
  queryKey: computed(() => ['student', 'topic', topicId.value, 'session']),
  queryFn: () => studentApi.createSession(topicId.value),
  staleTime: Infinity,
  retry: false,
})
const sessionId = computed(() => sessionQuery.data.value?.session_id ?? '')

// 2. 拿歷史訊息
const messagesQuery = useQuery({
  queryKey: computed(() => studentKeys.messages(sessionId.value)),
  queryFn: () => studentApi.getSessionMessages(sessionId.value),
  enabled: () => !!sessionId.value,
  retry: false,
  // 串流進行中不要被重新整理的資料蓋掉
  refetchOnWindowFocus: false,
})

const messages = ref<DisplayMessage[]>([])
const remaining = ref(0)
const total = ref(0)
const completed = ref(false)

watch(
  () => messagesQuery.data.value,
  (data) => {
    if (!data) return
    messages.value = data.messages.map((m) => ({ ...m }))
    remaining.value = data.remaining_rounds
    total.value = data.max_rounds
    completed.value = data.status === 'COMPLETED'
  },
  { immediate: true },
)

const loading = computed(() => sessionQuery.isPending.value || messagesQuery.isPending.value)
const loadError = computed(() => sessionQuery.error.value ?? messagesQuery.error.value)
function retryLoad() {
  if (sessionQuery.isError.value) void sessionQuery.refetch()
  else void messagesQuery.refetch()
}

// 3. 送出訊息、接收串流
const { isStreaming, streamMessage } = useChatStream()
const draft = ref('')
const sendError = ref('')
const listEnd = useTemplateRef<HTMLElement>('listEnd')

function scrollToBottom() {
  void nextTick(() => listEnd.value?.scrollIntoView({ block: 'end', behavior: 'smooth' }))
}
watch(() => messages.value.length, scrollToBottom)

async function handleSend(text: string) {
  if (!sessionId.value || isStreaming.value) return
  sendError.value = ''
  draft.value = ''
  const stamp = Date.now()
  const userId = `local-${stamp}`
  const replyId = `reply-${stamp}`
  messages.value.push({ message_id: userId, role: 'user', content: text })
  messages.value.push({ message_id: replyId, role: 'assistant', content: '', pending: true })
  // 拿 reactive 版本的物件來改，畫面才會跟著更新
  const replyMessage = messages.value[messages.value.length - 1] as DisplayMessage

  try {
    await streamMessage(sessionId.value, text, {
      onChunk: (chunk) => {
        replyMessage.pending = false
        replyMessage.content += chunk
        scrollToBottom()
      },
      onDone: (done) => {
        replyMessage.message_id = done.message_id
        remaining.value = done.remaining_rounds
        completed.value = done.is_completed
      },
    })
    replyMessage.pending = false
    if (completed.value) {
      void queryClient.invalidateQueries({ queryKey: studentKeys.course(courseId.value) })
    }
  } catch (err) {
    messages.value = messages.value.filter(
      (m) => m.message_id !== userId && m !== replyMessage && m.message_id !== replyId,
    )
    draft.value = text
    sendError.value = getApiErrorMessage(err, '導魷沒有回應，請再送一次')
  }
}

// 4. 語音輸入
const voice = useVoiceRecorder()
async function handleMic() {
  try {
    const text = await voice.toggleRecording()
    if (text) draft.value = draft.value ? `${draft.value} ${text}` : text
  } catch {
    // 錯誤訊息在 voice.errorMessage
  }
}

const studentName = computed(() => authStore.user?.name ?? '學生')
</script>

<template>
  <div class="flex min-h-full flex-1 flex-col">
    <div class="mx-auto w-full max-w-[870px] flex-1 px-4 pb-6 pt-8 sm:pt-10">
      <h1 class="mb-8 text-center text-h1-title text-foreground">{{ topic?.title ?? '…' }}</h1>

      <QueryState
        :loading="loading"
        :error="loadError"
        error-text="無法進入對話"
        :skeleton-count="2"
        @retry="retryLoad"
      >
        <ol class="flex flex-col gap-6" aria-label="對話紀錄" aria-live="polite">
          <li
            v-for="message in messages"
            :key="message.message_id"
            class="flex"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <ChatBubble
              :from="message.role === 'user' ? 'student' : 'ai'"
              :name="message.role === 'user' ? studentName : undefined"
              :pending="message.pending"
            >
              {{ message.content }}
            </ChatBubble>
          </li>
        </ol>

        <div
          v-if="completed"
          class="mt-8 flex flex-col items-center gap-4 rounded-2xl border border-border bg-card p-6 text-center shadow-elevated"
        >
          <p class="text-h2-title leading-normal text-foreground">這次的對話結束了！</p>
          <p class="text-body-lg text-muted-foreground">
            看看你的想法被歸到哪一類，還有其他同學怎麼想。
          </p>
          <Button as-child size="lg">
            <RouterLink :to="{ name: 'StudentResult', params: { courseId, sessionId } }"
              >查看結果</RouterLink
            >
          </Button>
        </div>
      </QueryState>
      <div ref="listEnd" />
    </div>

    <div class="sticky bottom-0 z-10">
      <p
        v-if="sendError || voice.errorMessage.value"
        role="alert"
        class="bg-background px-4 pt-2 text-center text-body text-destructive"
      >
        {{ sendError || voice.errorMessage.value }}
      </p>
      <ChatInput
        v-if="!completed"
        v-model="draft"
        :remaining="total ? remaining : undefined"
        :total="total || undefined"
        :sending="isStreaming"
        :disabled="loading || !!loadError"
        :recording="voice.isRecording.value"
        :transcribing="voice.isTranscribing.value"
        @send="handleSend"
        @mic="handleMic"
      />
    </div>
  </div>
</template>
