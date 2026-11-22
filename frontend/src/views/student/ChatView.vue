<script setup lang="ts">
import AppBanner from '@/components/common/AppBanner.vue'
/**
 * 學生：和導魷對話。對應 Figma「P07_Student_Question」（node 171:280）。
 * API（docs/API功能規格.md v0.2「題目對話階段」）：
 *   GET  /courses/{courseId}/topics                 題目名稱、本人的 session_id
 *   POST /topics/{topicId}/sessions                 第一次進入時建立 Session
 *   GET  /sessions/{sessionId}/messages             歷史訊息、回合數
 *   POST /sessions/{sessionId}/messages/stream      送出回答，SSE 逐段接收回覆
 *   POST /sessions/{sessionId}/end                  結束對話：complete／continue（達成目標時的選擇）、finish（提早結束）
 * 結束規則（後端 #267、負責人決定）：
 *   - AI 判斷達成目標（awaiting_end_consent）→ 跳出 Figma「Frame 1013」的視窗「導魷覺得心滿意足」：
 *     結束對話＝complete，繼續對話（或關掉視窗）＝continue
 *   - 技術債：後端在學生按過「繼續」後每一回合還是會再設 awaiting_end_consent。
 *     暫時由前端記住「這段對話按過繼續」（localStorage），之後不再自動跳出；學生要結束就按右上的按鈕。
 *     後端提供對應欄位後改用後端的值，拿掉 consentDeclined。
 *   - 回合用完 → 後端自動結束（session_status: ended、ending_reason: turn_limit），不用學生按
 *   - 學生回答 3 次後（can_finish_early）或已經達成目標時，標題列右上出現「提早結束」：
 *     已經達成目標 → 打開同一個「導魷覺得心滿意足」視窗（結束＝complete，結束原因記成達成目標）；
 *     還沒達成 → 先確認再送 finish
 *   - 不提供「放棄」：沒回答滿 3 次的學生直接離開就好，對話留著之後可以回來（後端的 abandon 不用）
 *   - 對話一結束（三種方式都一樣）：最後一句顯示完後，對話最下面出現一條從中間往左右展開的分隔線
 *     「回合結束，正在製作報告」（像 Discord 的換日線），停 3 秒讓學生看完最後一句，再跳到個人報告頁
 *     （報告頁本身會顯示「正在整理」並自動更新，所以不用等報告做好）；已經結束的對話打開時直接跳過去
 *   - completed、ended 後端都會自動開始產生報告；這裡還是會呼叫一次 startReport（可重複呼叫），相容還沒更新的後端
 * 語音輸入用瀏覽器內建的語音辨識（useSpeechInput）；AI 訊息下面的喇叭用瀏覽器語音朗讀。
 */
import { computed, nextTick, onBeforeUnmount, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { courseKeys } from '@/api/courses'
import {
  sessionKeys,
  sessionsApi,
  type DialogueStatus,
  type EndingReason,
  type SessionMessage,
} from '@/api/sessions'
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
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

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
/** 對話結束後直接到這裡 */
const reportLink = computed(() => ({
  name: 'StudentReport',
  params: { courseId: courseId.value, sessionId: sessionId.value, tab: 'personal' },
}))

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
const status = ref<DialogueStatus>('open')
const endingReason = ref<EndingReason | null>(null)
/** AI 判斷達成目標、等學生選擇 */
const awaitingConsent = ref(false)
/** 學生已經回答 3 次以上：可以提早結束 */
const canFinishEarly = ref(false)
/** AI 判斷達成過目標（一旦達成就一直是 true） */
const goalReached = ref(false)
/** 結束分隔線停留多久再跳到報告頁 */
const ENDING_DELAY_MS = 3000
/** 正在顯示結束分隔線、等待跳轉 */
const ending = ref(false)
let endingTimer: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(endingTimer))

/** 對話結束、可以看報告了（達成目標後結束，或回合用完／提早結束） */
const finished = computed(() => status.value === 'completed' || status.value === 'ended')

watch(
  () => messagesQuery.data.value,
  (data) => {
    if (!data) return
    messages.value = data.messages.map((m) => ({ ...m }))
    maxTurns.value = data.max_turns ?? 0
    usedTurns.value = data.completed_turns
    status.value = data.session_status
    endingReason.value = data.ending_reason ?? null
    awaitingConsent.value = data.session_status === 'open' && data.awaiting_end_consent
    canFinishEarly.value = !!data.can_finish_early
    goalReached.value = !!data.goal_reached
    // 已經結束的對話（重新整理、從別的頁面進來）：直接到報告頁；正在播結束動畫時不打斷
    if ((data.session_status === 'completed' || data.session_status === 'ended') && !ending.value)
      markFinished(false)
  },
  { immediate: true },
)

const loading = computed(
  () => !course.value || sessionQuery.isPending.value || messagesQuery.isPending.value,
)
const loadError = computed(() => sessionQuery.error.value ?? messagesQuery.error.value)
/** 不能再回答：放棄了、老師產生摘要時被關閉，或題目已經進入摘要階段 */
const closed = computed(
  () =>
    status.value === 'abandoned' ||
    status.value === 'closed_by_summary' ||
    (topic.value?.topic_status === 'summary' && !finished.value),
)

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
 * 對話結束：更新課程頁的活動狀態，確保報告開始產生，然後到個人報告頁。
 * 新的後端結束時就會自動開始產生報告；舊的後端要呼叫 startReport 才會開始。可以重複呼叫，不會重做。
 * animate：剛在這一頁結束的 → 先顯示結束分隔線、停 3 秒；打開時就已經結束的 → 直接跳。
 * 用 replace：按上一頁不會回到已經結束的對話頁。
 */
function markFinished(animate = true) {
  if (ending.value) return
  void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
  void sessionsApi.startReport(sessionId.value).catch(() => undefined)
  if (!animate) {
    void router.replace(reportLink.value)
    return
  }
  ending.value = true
  scrollToBottom()
  endingTimer = setTimeout(() => void router.replace(reportLink.value), ENDING_DELAY_MS)
}
const endingText = computed(() =>
  endingReason.value === 'teacher_ended_stage2'
    ? t('chat.endingTeacher')
    : endingReason.value === 'turn_limit'
      ? t('chat.endingTurnLimit')
      : endingReason.value === 'student_requested_stop'
        ? t('chat.endingEarly')
        : t('chat.endingGoal'),
)

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
        if (done.session_status) status.value = done.session_status
        else if (done.is_completed) status.value = 'completed'
        endingReason.value = done.ending_reason ?? null
        awaitingConsent.value = status.value === 'open' && done.awaiting_end_consent
        canFinishEarly.value = !!done.can_finish_early
        if (done.goal_reached !== undefined) goalReached.value = done.goal_reached
      },
    })
    reply.pending = false
    pendingRequest = null
    if (finished.value) markFinished()
  } catch (err) {
    // 斷線或失敗：用後端的紀錄校準
    // - 回合數增加：回覆其實已經存好了
    // - 狀態變了：例如老師結束了對話（ended，回合數不變），或對話被關閉 → 照後端的狀態，不能再回答
    const fresh = await sessionsApi.messages(sessionId.value).catch(() => null)
    if (
      fresh &&
      (fresh.completed_turns > usedTurns.value || fresh.session_status !== status.value)
    ) {
      pendingRequest = null
      if (fresh.session_status === 'completed' || fresh.session_status === 'ended') {
        // 先開始結束流程（顯示分隔線、3 秒後到報告頁），再換成後端的紀錄
        endingReason.value = fresh.ending_reason ?? null
        markFinished()
      }
      queryClient.setQueryData(sessionKeys.messages(sessionId.value), fresh)
      return
    }
    messages.value = messages.value.filter((m) => !m.message_id.endsWith(`-${stamp}`))
    draft.value = text
    sendError.value = getApiErrorMessage(err, t('chat.noReply'))
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

// 5. 達成目標：問學生要結束還是繼續。關掉視窗（Esc、點背景、按「繼續對話」）都算繼續
// 技術債：「按過繼續」先記在瀏覽器（見檔案開頭），按過就不再自動跳出
const declinedKey = computed(() => `chat:consent-declined:${sessionId.value}`)
const consentDeclined = ref(false)
watch(
  declinedKey,
  (key) => {
    try {
      consentDeclined.value = localStorage.getItem(key) === '1'
    } catch {
      consentDeclined.value = false
    }
  },
  { immediate: true },
)
function rememberDeclined() {
  consentDeclined.value = true
  try {
    localStorage.setItem(declinedKey.value, '1')
  } catch {
    // 瀏覽器不讓存就算了：最多只是之後又跳出一次
  }
}
const consentOpen = ref(false)
const consentError = ref('')
function openConsent() {
  consentError.value = ''
  consentOpen.value = true
}
watch(
  [awaitingConsent, isStreaming, consentDeclined],
  ([awaiting, streaming, declined]) => {
    if (awaiting && !streaming && !declined) openConsent()
  },
  { immediate: true },
)
type EndResult = Awaited<ReturnType<typeof sessionsApi.end>>
function applyEnd(result: EndResult) {
  status.value = result.session_status
  endingReason.value = result.ending_reason ?? null
  awaitingConsent.value = false
  canFinishEarly.value = !!result.can_finish_early
  void queryClient.invalidateQueries({ queryKey: sessionKeys.messages(sessionId.value) })
}
const endNow = useMutation({
  mutationFn: () => sessionsApi.end(sessionId.value, 'complete'),
  onSuccess: (result) => {
    consentOpen.value = false
    applyEnd(result)
    if (finished.value) markFinished()
  },
  onError: (err) => (consentError.value = getApiErrorMessage(err, t('chat.endFailed'))),
})
const keepGoing = useMutation({
  mutationFn: () => sessionsApi.end(sessionId.value, 'continue'),
  onSuccess: applyEnd,
  onError: (err) => (sendError.value = getApiErrorMessage(err, t('chat.continueFailed'))),
})
watch(consentOpen, (isOpen) => {
  // 學生沒選「結束」就關掉視窗 → 繼續對話，記下來之後不再自動跳出
  if (isOpen || endNow.isPending.value || finished.value) return
  rememberDeclined()
  if (awaitingConsent.value) {
    awaitingConsent.value = false
    keepGoing.mutate()
  }
})

// 6. 提早結束：回答滿 3 次後才能用，先確認再送 finish
const finishOpen = ref(false)
const finishError = ref('')
/** 右上的按鈕：已經達成目標 → 打開「導魷覺得心滿意足」；還沒達成 → 提早結束的確認 */
function onFinishButton() {
  if (goalReached.value) openConsent()
  else askFinish()
}
function askFinish() {
  finishError.value = ''
  finishOpen.value = true
}
const finishEarly = useMutation({
  mutationFn: () => sessionsApi.end(sessionId.value, 'finish'),
  onSuccess: (result) => {
    finishOpen.value = false
    applyEnd(result)
    if (finished.value) markFinished()
  },
  onError: (err) => (finishError.value = getApiErrorMessage(err, t('chat.finishEarlyFailed'))),
})

const studentName = computed(() => authStore.user?.name ?? t('common.student'))
const remaining = computed(() => Math.max(0, maxTurns.value - usedTurns.value))
</script>

<template>
  <div class="flex min-h-full flex-1 flex-col">
    <div class="mx-auto w-full max-w-[1200px] flex-1 px-4 pt-[30px] pb-6">
      <PageTitle
        :title="t('chat.title', { title: topic?.title ?? '…' })"
        :breadcrumbs="[
          { label: t('common.myCourses'), to: { name: 'StudentCourses' } },
          {
            label: course?.name ?? t('common.course'),
            to: { name: 'StudentCourse', params: { courseId } },
          },
        ]"
      >
        <template
          v-if="sessionId && (canFinishEarly || goalReached) && !finished && !closed"
          #after-title
        >
          <!-- 照 Figma：主色按鈕，靠右、跟對話框右邊對齊（對話框最寬 1000px、置中） -->
          <Button
            size="sm"
            class="ml-auto lg:mr-[max(0px,calc((100%-1000px)/2))]"
            :disabled="isStreaming || finishEarly.isPending.value || endNow.isPending.value"
            @click="onFinishButton"
            >{{ t('chat.finishEarly') }}</Button
          >
        </template>
      </PageTitle>
      <QueryState
        class="mx-auto mt-4 max-w-[1000px]"
        :loading="loading"
        :error="loadError"
        :error-text="t('chat.loadError')"
        :skeleton-count="2"
        @retry="retryLoad"
      >
        <ol
          :class="[cardClass, 'flex flex-col gap-[22px] px-4 py-2 sm:px-5']"
          :aria-label="t('chat.log')"
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
          <li v-if="ending" class="chat-ending flex items-center gap-4 py-3" role="status">
            <span
              class="chat-ending-line chat-ending-left h-px flex-1 bg-border"
              aria-hidden="true"
            />
            <span class="chat-ending-text shrink-0 text-body text-muted-foreground">{{
              endingText
            }}</span>
            <span
              class="chat-ending-line chat-ending-right h-px flex-1 bg-border"
              aria-hidden="true"
            />
          </li>
        </ol>

        <div
          v-if="closed"
          :class="[cardClass, 'mt-4 flex flex-col items-center gap-4 p-6 text-center']"
        >
          <p class="text-h2-title text-foreground">
            {{ status === 'abandoned' ? t('chat.abandoned') : t('chat.closed') }}
          </p>
        </div>
      </QueryState>
      <div ref="listEnd" />
    </div>

    <ConfirmDialog
      v-model:open="consentOpen"
      :title="t('chat.goalReachedTitle')"
      :description="t('chat.goalReachedDescription')"
      :confirm-text="t('chat.endNow')"
      :cancel-text="t('chat.keepGoing')"
      destructive
      confirm-first
      :loading="endNow.isPending.value"
      :error="consentError"
      @confirm="endNow.mutate()"
    />

    <ConfirmDialog
      v-model:open="finishOpen"
      :title="t('chat.finishEarlyTitle')"
      :description="t('chat.finishEarlyDescription')"
      :confirm-text="t('chat.finishEarlyConfirm')"
      :loading="finishEarly.isPending.value"
      :error="finishError"
      @confirm="finishEarly.mutate()"
    />

    <div class="sticky bottom-0 z-10">
      <div v-if="sendError || speech.errorMessage.value" class="bg-background px-4 pt-2">
        <AppBanner type="error">{{ sendError || speech.errorMessage.value }}</AppBanner>
      </div>
      <ChatInput
        v-if="!finished && !closed"
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

<style scoped>
/* 結束分隔線：兩條線從中間往左右展開，文字淡入 */
@media (prefers-reduced-motion: no-preference) {
  .chat-ending-line {
    animation: chat-ending-grow 600ms ease-out both;
  }
  .chat-ending-left {
    transform-origin: right;
  }
  .chat-ending-right {
    transform-origin: left;
  }
  .chat-ending-text {
    animation: chat-ending-fade 400ms ease-out 200ms both;
  }
}
@keyframes chat-ending-grow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}
@keyframes chat-ending-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
