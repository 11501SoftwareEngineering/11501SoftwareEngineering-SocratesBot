<script setup lang="ts">
/**
 * 探索結果報告 →「個人報告」分頁。對應 Figma「P08_Student_Result_01」（node 787:3003）。
 * API：先 POST /sessions/{sessionId}/report 開始產生（結束對話不會自動產生；可以重複呼叫，
 * 已經在做或做好了就直接回傳），之後用 GET 每 3 秒查進度。失敗時學生按「重新產生」再 POST 一次。
 * 不用 POST 輪詢：上次失敗時每 POST 一次就會重做一次。
 */
import { computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { reportPollInterval, sessionKeys, sessionsApi } from '@/api/sessions'
import QueryState from '@/components/common/QueryState.vue'
import PersonalReport from '@/components/report/PersonalReport.vue'
import { SpinnerIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { cardClass } from '@/lib/ui'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ sessionId: string }>()
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

const retry = useMutation({
  mutationFn: () => sessionsApi.startReport(props.sessionId),
  onSuccess: (result) => queryClient.setQueryData(sessionKeys.report(props.sessionId), result),
})
</script>

<template>
  <QueryState :loading="isPending" :error="error" error-text="無法取得個人報告" @retry="refetch()">
    <div :class="[cardClass, 'px-5 py-6 sm:px-10']">
      <PersonalReport
        v-if="data?.report_status === 'ready' && data.report"
        :report="data.report"
        :name="authStore.user?.name ?? '我'"
        :message-text="messageText"
      />
      <div
        v-else-if="data?.report_status === 'failed'"
        class="flex flex-col items-center gap-4 py-10 text-center"
      >
        <p class="text-h2-title text-foreground">報告產生失敗</p>
        <p class="text-body-lg text-muted-foreground">可能是 AI 服務暫時有問題，請再試一次。</p>
        <Button :disabled="retry.isPending.value" @click="retry.mutate()">重新產生報告</Button>
      </div>
      <div v-else class="flex flex-col items-center gap-3 py-10 text-center" role="status">
        <SpinnerIcon class="animate-spin" />
        <p class="text-h2-title text-foreground">導魷正在整理你的報告…</p>
        <p class="text-body-lg text-muted-foreground">通常不到一分鐘，這個頁面會自動更新。</p>
      </div>
    </div>
  </QueryState>
</template>
