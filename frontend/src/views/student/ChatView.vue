<script setup lang="ts">
/**
 * 學生：和導魷對話。對應 Figma「P07_Student_Question」（node 171:280）。
 * API（docs/API功能規格.md v0.2「題目對話階段」）：
 *   GET  /courses/{courseId}/topics                 題目名稱、本人的 session_id
 *   POST /topics/{topicId}/sessions                 第一次進入時建立 Session
 *   GET  /sessions/{sessionId}/messages             歷史訊息、回合數
 *   POST /sessions/{sessionId}/messages/stream      送出回答，SSE 逐段接收回覆
 *   POST /sessions/{sessionId}/end                  放棄探究（abandon），之後回課程頁，照 Prototype
 * 只在回合用完時結束：AI 組還沒定「達成目標提早結束」的規則，所以不處理 awaiting_end_consent
 * （不顯示「要結束這次探究嗎？」，也不送 complete／continue）。
 * 語音輸入用瀏覽器內建的語音辨識（useSpeechInput）；AI 訊息下面的喇叭用瀏覽器語音朗讀。
 */
import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { courseKeys } from '@/api/courses'
import { sessionKeys, sessionsApi, type SessionMessage } from '@/api/sessions'
import ChatBubble from '@/components/common/ChatBubble.vue'
import ChatInput from '@/components/common/ChatInput.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import SpeakButton from '@/components/common/SpeakButton.vue'
import { Button } from '@/components/ui/button'
import { useChatStream } from '@/composables/useChatStream'
import { useCourseTopics } from '@/composables/useCourse'
import { useSpeechInput } from '@/composables/useSpeechInput'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass } from '@/lib/ui'
import { useAuthStore } from '@/stores/auth'

interface DisplayMessage extends SessionMessage {
  pending?: boolean
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const topicId = computed(() => String(route.params.topicId ?? ''))

const { data: course } = useCourseTopics(courseId)
const topic = computed(() => course.value?.topics.find((t) => t.topic_id === topicId.value))

// 1. 找到本人的 Session：列表有 session_id 就用，沒有就建立一個
const sessionQuery = useQuery({
  queryKey: computed(() => ['topics', topicId.value, 'my-session', topic.value?.session_id ?? '']),
  enabled: () => !!topic.value,
  queryFn: async () =>
    topic.value?.session_id ?? (await sessionsApi.create(topicId.value)).session_id,
  staleTime: Infinity,
  retry: false,
})
const sessionId = computed(() => sessionQuery.data.value ?? '')

// 2. 歷史訊息
const messagesQuery = useQuery({
  queryKey: computed(() => sessionKeys.messages(sessionId.value)),
  queryFn: () => sessionsApi.messages(sessionId.value),
  enabled: () => !!sessionId.value,
  retry: false,
  // 串流進行中不要被重新整理的資料蓋掉
  refetchOnWindowFocus: false,
})

const messages = ref<DisplayMessage[]>([])
const maxTurns = ref(0)
const usedTurns = ref(0)
const completed = ref(false)

watch(
  () => messagesQuery.data.value,
  (data) => {
    if (!data) return
    messages.value = data.messages.map((m) => ({ ...m }))
    maxTurns.value = data.max_turns
    usedTurns.value = data.completed_turns
    completed.value = data.session_status === 'COMPLETED'
  },
  { immediate: true },
)

const loading = computed(
  () => !course.value || sessionQuery.isPending.value || messagesQuery.isPending.value,
)
const loadError = computed(() => sessionQuery.error.value ?? messagesQuery.error.value)
const closed = computed(() => topic.value?.topic_status === 'summary' && !completed.value)

function retryLoad() {
  if (sessionQuery.isError.value) void sessionQuery.refetch()
  else void messagesQuery.refetch()
}

// 3. 送出訊息、接收串流
const { isStreaming, streamMessage } = useChatStream()
const draft = ref('')
const sendError = ref('')
/** 送出失敗時留著，重送同一則回答要用同一個 request_id */
let pendingRequest: { text: string; id: string } | null = null
const listEnd = useTemplateRef<HTMLElement>('listEnd')

function scrollToBottom() {
  void nextTick(() => listEnd.value?.scrollIntoView({ block: 'end', behavior: 'smooth' }))
}
watch(() => messages.value.length, scrollToBottom)

/**
 * 對話完成：更新課程頁的活動狀態，並請後端開始產生個人報告。
 * 結束對話不會自動產生報告，一定要呼叫 startReport；這樣學生看「探究結束」畫面時報告已經在做了。
 * 這裡失敗不要緊：進個人報告頁時還會再呼叫一次（可以重複呼叫，不會重做）。
 */
function markFinished() {
  void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
  void sessionsApi.startReport(sessionId.value).catch(() => undefined)
}

async function handleSend(text: string) {
  if (!sessionId.value || isStreaming.value) return
  speech.cancel() // 送出時還在聽的話就停掉，不然辨識結果會再填回輸入框
  sendError.value = ''
  draft.value = ''
  const requestId = pendingRequest?.text === text ? pendingRequest.id : crypto.randomUUID()
  pendingRequest = { text, id: requestId }
  const stamp = Date.now()
  const now = new Date().toISOString()
  messages.value.push({
    message_id: `local-${stamp}`,
    sender: 'student',
    content: text,
    created_at: now,
  })
  messages.value.push({
    message_id: `reply-${stamp}`,
    sender: 'ai',
    content: '',
    created_at: now,
    pending: true,
  })
  // 拿 reactive 版本的物件來改，畫面才會跟著更新
  const reply = messages.value[messages.value.length - 1] as DisplayMessage

  try {
    await streamMessage(sessionId.value, text, requestId, {
      onChunk: (chunk) => {
        reply.pending = false
        reply.content += chunk
        scrollToBottom()
      },
      onDone: (done) => {
        reply.message_id = done.message_id
        usedTurns.value = done.completed_turns
        completed.value = done.is_completed
      },
    })
    reply.pending = false
    pendingRequest = null
    if (completed.value) markFinished()
  } catch (err) {
    // 斷線或失敗：用後端的紀錄校準（回覆可能其實已經存好了）
    const fresh = await sessionsApi.messages(sessionId.value).catch(() => null)
    if (fresh && fresh.completed_turns > usedTurns.value) {
      queryClient.setQueryData(sessionKeys.messages(sessionId.value), fresh)
      pendingRequest = null
      if (fresh.session_status === 'COMPLETED') markFinished()
      return
    }
    messages.value = messages.value.filter((m) => !m.message_id.endsWith(`-${stamp}`))
    draft.value = text
    sendError.value = getApiErrorMessage(err, '導魷沒有回應，請再送一次')
  }
}

// 4. 語音輸入：開始說話前輸入框已經有的文字保留在前面，後面接辨識出來的內容
let draftBeforeSpeech = ''
const speech = useSpeechInput({
  onText: (text) => {
    draft.value = draftBeforeSpeech ? `${draftBeforeSpeech} ${text}` : text
  },
})
function handleMic() {
  if (!speech.isListening.value) draftBeforeSpeech = draft.value.trim()
  speech.toggle()
}

// 5. 放棄探究：保留不算完成，回到課程頁（照 Prototype 的 P07）
const abandonOpen = ref(false)
const abandon = useMutation({
  mutationFn: () => sessionsApi.end(sessionId.value, 'abandon'),
  onSuccess: async () => {
    abandonOpen.value = false
    queryClient.removeQueries({ queryKey: ['topics', topicId.value, 'my-session'] })
    await queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
    await router.push({ name: 'StudentCourse', params: { courseId: courseId.value } })
  },
  onError: (err) => {
    abandonOpen.value = false
    sendError.value = getApiErrorMessage(err, '放棄失敗，請稍後再試')
  },
})

const studentName = computed(() => authStore.user?.name ?? '學生')
const remaining = computed(() => Math.max(0, maxTurns.value - usedTurns.value))
const reportLink = computed(() => ({
  name: 'StudentReport',
  params: { courseId: courseId.value, sessionId: sessionId.value, tab: 'personal' },
}))
</script>

<template>
  <div class="flex min-h-full flex-1 flex-col">
    <div class="mx-auto w-full max-w-[1200px] flex-1 px-4 pt-[30px] pb-6">
      <PageTitle
        :title="`探索活動 - ${topic?.title ?? '…'}`"
        :breadcrumbs="[
          { label: '我的課程', to: { name: 'StudentCourses' } },
          { label: course?.name ?? '課程', to: { name: 'StudentCourse', params: { courseId } } },
        ]"
      >
        <template v-if="sessionId && !completed && !closed" #after-title>
          <Button
            variant="secondary"
            size="sm"
            :disabled="isStreaming || abandon.isPending.value"
            @click="abandonOpen = true"
            >放棄探究</Button
          >
        </template>
      </PageTitle>
      <QueryState
        class="mx-auto mt-4 max-w-[1000px]"
        :loading="loading"
        :error="loadError"
        error-text="無法進入對話"
        :skeleton-count="2"
        @retry="retryLoad"
      >
        <ol
          :class="[cardClass, 'flex flex-col gap-[22px] px-4 py-2 sm:px-5']"
          aria-label="對話紀錄"
          aria-live="polite"
        >
          <li v-for="message in messages" :key="message.message_id" class="flex flex-col">
            <ChatBubble
              :from="message.sender"
              :name="message.sender === 'student' ? studentName : undefined"
              :pending="message.pending"
              >{{ message.content }}
              <template v-if="message.sender === 'ai' && !message.pending" #after>
                <SpeakButton :id="message.message_id" :text="message.content" />
              </template>
            </ChatBubble>
          </li>
        </ol>

        <div
          v-if="completed || closed"
          :class="[cardClass, 'mt-4 flex flex-col items-center gap-4 p-6 text-center']"
        >
          <p class="text-h2-title text-foreground">
            {{ completed ? '這次的探究結束了！' : '老師已經結束這個活動的作答' }}
          </p>
          <p v-if="completed" class="text-body-lg text-muted-foreground">
            導魷正在整理你的個人報告，看看你的想法怎麼變化。
          </p>
          <Button v-if="completed" as-child size="lg">
            <RouterLink :to="reportLink">查看個人報告</RouterLink>
          </Button>
        </div>
      </QueryState>
      <div ref="listEnd" />
    </div>

    <ConfirmDialog
      v-model:open="abandonOpen"
      title="放棄這次探究？"
      description="放棄後這次的對話不算完成，也不會產生個人報告。之後可以從課程頁重新開始。"
      confirm-text="放棄"
      destructive
      :loading="abandon.isPending.value"
      @confirm="abandon.mutate()"
    />

    <div class="sticky bottom-0 z-10">
      <p
        v-if="sendError || speech.errorMessage.value"
        role="alert"
        class="bg-background px-4 pt-2 text-center text-body text-destructive"
      >
        {{ sendError || speech.errorMessage.value }}
      </p>
      <ChatInput
        v-if="!completed && !closed"
        v-model="draft"
        :remaining="maxTurns ? remaining : undefined"
        :total="maxTurns || undefined"
        :sending="isStreaming"
        :disabled="loading || !!loadError"
        :show-mic="speech.supported"
        :recording="speech.isListening.value"
        @send="handleSend"
        @mic="handleMic"
      />
    </div>
  </div>
</template>
