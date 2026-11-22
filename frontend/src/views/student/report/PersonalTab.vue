<script setup lang="ts">
/**
 * 探索結果報告 →「個人報告」分頁。對應 Figma「P08_Student_Result_01」（node 787:3003）。
 * API：先 POST /sessions/{sessionId}/report 開始產生（結束對話不會自動產生；可以重複呼叫，
 * 已經在做或做好了就直接回傳），之後用 GET 每 3 秒查進度。失敗時學生按「重新產生」再 POST 一次。
 * 不用 POST 輪詢：上次失敗時每 POST 一次就會重做一次。
 *
 * 錯誤分三種，給不同的下一步：
 *   報告產生失敗（report_status: failed）→「重新產生報告」
 *   拿不到這份報告（沒權限／找不到對話／對話還沒完成：401、403、404、409）→ 顯示原因，「回到課程」
 *   網路或伺服器錯誤 →「重新載入」
 */
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import axios from 'axios'
import { CircleAlert } from '@lucide/vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { reportPollInterval, sessionKeys, sessionsApi } from '@/api/sessions'
import QueryState from '@/components/common/QueryState.vue'
import PersonalReport from '@/components/report/PersonalReport.vue'
import { SpinnerIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { cardClass } from '@/lib/ui'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{ sessionId: string }>()
const route = useRoute()
const authStore = useAuthStore()
const queryClient = useQueryClient()

/** 這個頁面已經 POST 過的對話；之後的輪詢只用 GET */
const started = new Set<string>()

const { data, isPending, error, refetch } = useQuery({
  queryKey: computed(() => sessionKeys.report(props.sessionId)),
  queryFn: async () => {
    const id = props.sessionId
    if (started.has(id)) return sessionsApi.report(id)
    const result = await sessionsApi.startReport(id)
    started.add(id)
    return result
  },
  refetchInterval: (query) => reportPollInterval(query.state.data),
  retry: false,
})

const messages = useQuery({
  queryKey: computed(() => sessionKeys.messages(props.sessionId)),
  queryFn: () => sessionsApi.messages(props.sessionId),
})
const messageText = computed(() =>
  Object.fromEntries((messages.data.value?.messages ?? []).map((m) => [m.message_id, m.content])),
)

/** 重新載入也不會好的錯誤：沒權限、找不到對話、對話還沒完成 */
const BLOCKED_STATUSES = [401, 403, 404, 409]
const blocked = computed(
  () =>
    axios.isAxiosError(error.value) && BLOCKED_STATUSES.includes(error.value.response?.status ?? 0),
)
const courseLink = computed(() => ({
  name: 'StudentCourse',
  params: { courseId: String(route.params.courseId ?? '') },
}))

const retry = useMutation({
  mutationFn: () => sessionsApi.startReport(props.sessionId),
  onSuccess: (result) => queryClient.setQueryData(sessionKeys.report(props.sessionId), result),
})
</script>

<template>
  <QueryState
    :loading="isPending"
    :error="error"
    :error-text="t('report.personalError')"
    @retry="refetch()"
  >
    <template v-if="blocked" #error="{ message }">
      <CircleAlert class="size-10 text-destructive" aria-hidden="true" />
      <p class="text-body-lg text-foreground">{{ message }}</p>
      <Button as-child variant="secondary">
        <RouterLink :to="courseLink">{{ t('report.backToCourse') }}</RouterLink>
      </Button>
    </template>
    <div :class="[cardClass, 'px-5 py-6 sm:px-10']">
      <PersonalReport
        v-if="data?.report_status === 'ready' && data.report"
        :report="data.report"
        :name="authStore.user?.name ?? t('report.me')"
        :message-text="messageText"
      />
      <div
        v-else-if="data?.report_status === 'failed'"
        class="flex flex-col items-center gap-4 py-10 text-center"
      >
        <p class="text-h2-title text-foreground">{{ t('report.failedTitle') }}</p>
        <p class="text-body-lg text-muted-foreground">{{ t('report.failedDescription') }}</p>
        <Button :disabled="retry.isPending.value" @click="retry.mutate()">{{
          t('report.retry')
        }}</Button>
        <p v-if="retry.error.value" role="alert" class="text-body text-destructive-dark">
          {{ getApiErrorMessage(retry.error.value, t('report.retryFailed')) }}
        </p>
      </div>
      <div v-else class="flex flex-col items-center gap-3 py-10 text-center" role="status">
        <SpinnerIcon class="animate-spin" />
        <p class="text-h2-title text-foreground">{{ t('report.preparingTitle') }}</p>
        <p class="text-body-lg text-muted-foreground">{{ t('report.preparingDescription') }}</p>
      </div>
    </div>
  </QueryState>
</template>
