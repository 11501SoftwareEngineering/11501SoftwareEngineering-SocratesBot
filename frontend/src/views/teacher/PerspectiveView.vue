<script setup lang="ts">
import AppBanner from '@/components/common/AppBanner.vue'
/**
 * 老師／助教：全班觀點。對應 Figma「P13-1_Teacher_Result」（摘要審閱）、「P13-2_Teacher_Result」（學生報告）、
 * 「P13_StudentReport」（學生報告細節）。
 *   上方：題目、「重新整理摘要」、完成人數／可用報告／觀點群組
 *   分頁：摘要審閱｜學生報告（網址 ?tab=reports&group=群組，可以直接分享篩選結果）
 * API：GET /topics/{topicId}/setup（題目）、GET /topics/{topicId}/reports、GET/POST /topics/{topicId}/summary、
 *      GET /topics/{topicId}/conversation-status、POST /topics/{topicId}/end-conversation（後端 #272）
 * 第一次：「結束對話並整理摘要」→ 先查還有幾個對話開著、跟老師確認 → 結束對話。
 *   還開著的對話會被結束（學生照樣有報告），後端先等個人報告好了再自動整理全班摘要。
 * 摘要都是背景整理：preparation_status 是 pending／processing 時每 3 秒查一次；failed 時可以重試。
 * 摘要相關的 API 後端只允許老師，所以整理摘要的按鈕只給老師。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { courseKeys } from '@/api/courses'
import { isPreparing, reportGroups, summariesApi, summaryKeys } from '@/api/summaries'
import { topicKeys, topicsApi } from '@/api/topics'
import ComingSoon from '@/components/common/ComingSoon.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import TabNav from '@/components/common/TabNav.vue'
import { DoughnutIcon, FileIcon, GroupIcon, RefreshIcon, SpinnerIcon } from '@/components/icons'
import StatTile from '@/components/report/StatTile.vue'
import { Button } from '@/components/ui/button'
import { useCourseTopics } from '@/composables/useCourse'
import { getApiErrorMessage } from '@/lib/utils'
import { pageClass } from '@/lib/ui'
import StudentReportsTab from './perspective/StudentReportsTab.vue'
import SummaryReviewTab from './perspective/SummaryReviewTab.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

type Tab = 'summary' | 'reports'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const topicId = computed(() => String(route.params.topicId ?? ''))

const { data: course } = useCourseTopics(courseId)
const topic = computed(() => course.value?.topics.find((t) => t.topic_id === topicId.value))
const isTeacher = computed(() => course.value?.my_role === 'teacher')
const can = (p: 'view_reports' | 'edit_summary' | 'edit_topics') =>
  isTeacher.value || (course.value?.my_permissions ?? []).includes(p)

const setup = useQuery({
  queryKey: computed(() => topicKeys.setup(topicId.value)),
  queryFn: () => topicsApi.getSetup(topicId.value),
  enabled: () => isTeacher.value || (course.value?.my_permissions ?? []).includes('edit_topics'),
  retry: false,
})
const title = computed(() => setup.data.value?.setup.core_question ?? topic.value?.title ?? '…')

const summary = useQuery({
  queryKey: computed(() => summaryKeys.summary(topicId.value)),
  queryFn: () => summariesApi.get(topicId.value),
  enabled: () => !!course.value && (can('view_reports') || can('edit_summary')),
  // 背景整理中：每 3 秒查一次進度
  refetchInterval: (query) => (isPreparing(query.state.data) ? 3000 : false),
})
const reports = useQuery({
  queryKey: computed(() => summaryKeys.reports(topicId.value)),
  queryFn: () => summariesApi.reports(topicId.value),
  enabled: () => !!course.value && can('view_reports'),
  // 結束對話後報告一份份產生：還有產生中的、或摘要還在整理時，每 3 秒更新
  refetchInterval: (query) =>
    (query.state.data?.processing_count ?? 0) > 0 || isPreparing(summary.data.value) ? 3000 : false,
})
const preparing = computed(() => isPreparing(summary.data.value))
const prepareFailed = computed(() => summary.data.value?.preparation_status === 'failed')

const groups = computed(() => reportGroups(summary.data.value?.summary))

const tab = computed<Tab>({
  get: () => (route.query.tab === 'reports' ? 'reports' : 'summary'),
  set: (value) =>
    void router.replace({
      query: { ...route.query, tab: value === 'summary' ? undefined : value },
    }),
})
const group = computed({
  get: () => String(route.query.group ?? ''),
  set: (value: string) =>
    void router.replace({ query: { ...route.query, group: value || undefined } }),
})
const tabs = computed(() => [
  { key: 'summary' as const, label: t('perspective.reviewTab') },
  ...(can('view_reports')
    ? [
        {
          key: 'reports' as const,
          label: t('perspective.reportsTab'),
          count: reports.data.value?.reports.length ?? 0,
        },
      ]
    : []),
])

const stats = computed(() => {
  const r = reports.data.value
  const s = summary.data.value?.summary
  // 結束的人數＝達成目標後結束（completed）＋回合用完／提早結束／老師結束（ended），都有報告
  const finishedCount = r ? r.completed_count + (r.ended_count ?? 0) : 0
  return [
    {
      label: t('perspective.completed'),
      value: r ? `${finishedCount}/${r.class_size}` : '—',
      icon: GroupIcon,
    },
    {
      label: t('perspective.readyReports'),
      value: r ? `${r.ready_count}/${finishedCount}` : '—',
      icon: FileIcon,
    },
    {
      label: t('perspective.groups'),
      value: s ? String(s.groups.length) : '—',
      icon: DoughnutIcon,
    },
  ]
})

// 整理摘要
const generateError = ref('')
/** 還在對話階段：第一次要先結束對話 */
const isFirstSummary = computed(() => summary.data.value?.topic_status === 'conversation')
const canGenerate = computed(() => isTeacher.value)

function refreshAll() {
  void queryClient.invalidateQueries({ queryKey: ['topics', topicId.value, 'summary'] })
  void queryClient.invalidateQueries({ queryKey: summaryKeys.reports(topicId.value) })
  void queryClient.invalidateQueries({ queryKey: summaryKeys.conversation(topicId.value) })
  void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
}

// 第一次：結束對話（先查還有幾個對話開著，跟老師確認）
const closeOpen = ref(false)
const closeError = ref('')
const conversation = useQuery({
  queryKey: computed(() => summaryKeys.conversation(topicId.value)),
  queryFn: () => summariesApi.conversationStatus(topicId.value),
  enabled: () => isTeacher.value && isFirstSummary.value,
})
const openCount = computed(() => conversation.data.value?.open_dialogue_count ?? 0)
async function askClose() {
  closeError.value = ''
  closeOpen.value = true
  await conversation.refetch()
}
const closeConversation = useMutation({
  mutationFn: () => summariesApi.endConversation(topicId.value),
  onSuccess: () => {
    closeOpen.value = false
    generateError.value = ''
    refreshAll()
  },
  onError: (err) => (closeError.value = getApiErrorMessage(err, t('perspective.closeFailed'))),
})

// 之後：重新整理摘要（背景處理，回來的是 pending）
const generate = useMutation({
  mutationFn: () => summariesApi.generate(topicId.value),
  onSuccess: (result) => {
    generateError.value = ''
    queryClient.setQueryData(summaryKeys.summary(topicId.value), result)
    refreshAll()
  },
  onError: (err) =>
    (generateError.value = getApiErrorMessage(err, t('perspective.generateFailed'))),
})

/**
 * 按鈕：還在對話階段 → 結束對話並整理；已經有草稿 → 重新整理；
 * 對話已經結束但第一版整理失敗 → 再呼叫一次 end-conversation（後端會重試）
 */
function onGenerate() {
  generateError.value = ''
  if (isFirstSummary.value) void askClose()
  else if (summary.data.value?.summary) generate.mutate()
  else closeConversation.mutate()
}
const busy = computed(
  () => preparing.value || generate.isPending.value || closeConversation.isPending.value,
)
const generateLabel = computed(() =>
  busy.value
    ? t('perspective.summarizing')
    : isFirstSummary.value
      ? t('perspective.endAndGenerate')
      : summary.data.value?.summary
        ? t('perspective.refresh')
        : t('perspective.retryPrepare'),
)
const closeDescription = computed(() =>
  openCount.value > 0
    ? t('perspective.closeDescriptionOpen', { count: openCount.value })
    : t('perspective.closeDescription'),
)
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      :title="t('perspective.title')"
      :breadcrumbs="[
        { label: t('common.myCourses'), to: { name: 'TeacherCourses' } },
        {
          label: course?.name ?? t('common.course'),
          to: { name: 'TeacherCourse', params: { courseId } },
        },
      ]"
    />

    <div class="mt-[23px] flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-h1-title text-foreground">{{ title }}</h2>
      <RouterLink
        v-if="topic?.topic_status === 'setup' && can('edit_topics')"
        :to="{ name: 'TeacherActivitySetup', params: { courseId, topicId } }"
        class="rounded text-body-lg text-muted-foreground underline outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >{{ t('perspective.editSetup') }}</RouterLink
      >
      <Button v-if="canGenerate" :disabled="busy" @click="onGenerate">
        <SpinnerIcon v-if="busy" class="animate-spin" />
        <RefreshIcon v-else />
        {{ generateLabel }}
      </Button>
    </div>
    <p v-if="preparing" role="status" class="mt-2 text-body text-muted-foreground">
      {{ t('perspective.generatingHint') }}
    </p>
    <AppBanner v-if="prepareFailed && !busy" type="error" class="mt-2">{{
      t('perspective.prepareFailed')
    }}</AppBanner>
    <AppBanner v-if="generateError" type="error" class="mt-2">{{ generateError }}</AppBanner>

    <dl class="mt-4 grid gap-4 sm:grid-cols-3">
      <StatTile
        v-for="s in stats"
        :key="s.label"
        :label="s.label"
        :value="s.value"
        :icon="s.icon"
      />
    </dl>

    <TabNav v-model="tab" class="mt-4" :items="tabs" :label="t('perspective.tabs')" />

    <section class="mt-4">
      <template v-if="tab === 'summary'">
        <QueryState
          :loading="summary.isPending.value"
          :error="summary.error.value"
          :error-text="t('perspective.summaryError')"
          @retry="summary.refetch()"
        >
          <SummaryReviewTab
            v-if="summary.data.value?.summary"
            :topic-id="topicId"
            :data="summary.data.value"
            :can-edit="can('edit_summary')"
            :is-teacher="isTeacher"
          />
          <ComingSoon
            v-else
            :title="preparing ? t('perspective.preparingTitle') : t('perspective.noSummaryTitle')"
          >
            {{
              preparing
                ? t('perspective.generatingHint')
                : isFirstSummary
                  ? t('perspective.noSummaryDescription')
                  : t('perspective.noSummaryClosed')
            }}
          </ComingSoon>
        </QueryState>
      </template>
      <QueryState
        v-else
        :loading="reports.isPending.value"
        :error="reports.error.value"
        :error-text="t('perspective.reportsError')"
        @retry="reports.refetch()"
      >
        <StudentReportsTab
          v-if="reports.data.value"
          v-model:group="group"
          :data="reports.data.value"
          :groups="groups"
        />
      </QueryState>
    </section>

    <ConfirmDialog
      v-model:open="closeOpen"
      :title="t('perspective.closeTitle')"
      :description="closeDescription"
      :confirm-text="t('perspective.closeConfirm')"
      :loading="closeConversation.isPending.value || conversation.isFetching.value"
      :error="closeError"
      destructive
      @confirm="closeConversation.mutate()"
    />
  </div>
</template>
