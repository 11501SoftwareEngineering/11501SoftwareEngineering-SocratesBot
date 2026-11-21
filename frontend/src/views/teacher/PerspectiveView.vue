<script setup lang="ts">
/**
 * 老師／助教：全班觀點。對應 Figma「P13-1_Teacher_Result」（摘要審閱）、「P13-2_Teacher_Result」（學生報告）、
 * 「P13_StudentReport」（學生報告細節）。
 *   上方：題目、「重新整理摘要」、完成人數／可用報告／觀點群組
 *   分頁：摘要審閱｜學生報告（網址 ?tab=reports&group=群組，可以直接分享篩選結果）
 * API：GET /topics/{topicId}/setup（題目）、GET /topics/{topicId}/reports、GET/POST /topics/{topicId}/summary
 * 第一次「產生摘要」會結束學生作答，所以先確認。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { courseKeys } from '@/api/courses'
import { summariesApi, summaryKeys } from '@/api/summaries'
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

const reports = useQuery({
  queryKey: computed(() => summaryKeys.reports(topicId.value)),
  queryFn: () => summariesApi.reports(topicId.value),
  enabled: () => !!course.value && can('view_reports'),
})
const summary = useQuery({
  queryKey: computed(() => summaryKeys.summary(topicId.value)),
  queryFn: () => summariesApi.get(topicId.value),
  enabled: () => !!course.value && (can('view_reports') || can('edit_summary')),
})

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
  { key: 'summary' as const, label: '摘要審閱' },
  ...(can('view_reports')
    ? [
        {
          key: 'reports' as const,
          label: '學生報告',
          count: reports.data.value?.reports.length ?? 0,
        },
      ]
    : []),
])

const stats = computed(() => {
  const r = reports.data.value
  const s = summary.data.value?.summary
  return [
    { label: '完成人數', value: r ? `${r.completed_count}/${r.class_size}` : '—', icon: GroupIcon },
    { label: '可用報告', value: r ? `${r.ready_count}/${r.completed_count}` : '—', icon: FileIcon },
    { label: '觀點群組', value: s ? String(s.groups.length) : '—', icon: DoughnutIcon },
  ]
})

// 產生（重新整理）摘要
const generateOpen = ref(false)
const generateError = ref('')
const isFirstSummary = computed(() => summary.data.value?.topic_status === 'conversation')
const canGenerate = computed(() => (isFirstSummary.value ? isTeacher.value : can('edit_summary')))
const generate = useMutation({
  mutationFn: () => summariesApi.generate(topicId.value),
  onSuccess: (result) => {
    generateOpen.value = false
    generateError.value = ''
    queryClient.setQueryData(summaryKeys.summary(topicId.value), result)
    void queryClient.invalidateQueries({ queryKey: ['topics', topicId.value, 'summary'] })
    void queryClient.invalidateQueries({ queryKey: summaryKeys.reports(topicId.value) })
    void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
  },
  onError: (err) => {
    generateOpen.value = false
    generateError.value = getApiErrorMessage(err, '整理摘要失敗，請稍後再試')
  },
})
function askGenerate() {
  if (isFirstSummary.value) generateOpen.value = true
  else generate.mutate()
}
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      title="全班觀點"
      :breadcrumbs="[
        { label: '我的課程', to: { name: 'TeacherCourses' } },
        { label: course?.name ?? '課程', to: { name: 'TeacherCourse', params: { courseId } } },
      ]"
    />

    <div class="mt-[23px] flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-h1-title text-foreground">{{ title }}</h2>
      <RouterLink
        v-if="topic?.topic_status === 'setup' && can('edit_topics')"
        :to="{ name: 'TeacherActivitySetup', params: { courseId, topicId } }"
        class="rounded text-body-lg text-muted-foreground underline outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >編輯設定</RouterLink
      >
      <Button v-if="canGenerate" :disabled="generate.isPending.value" @click="askGenerate">
        <SpinnerIcon v-if="generate.isPending.value" class="animate-spin" />
        <RefreshIcon v-else />
        {{
          generate.isPending.value
            ? '整理中…'
            : summary.data.value?.summary
              ? '重新整理摘要'
              : '產生全班摘要'
        }}
      </Button>
    </div>
    <p v-if="generate.isPending.value" role="status" class="mt-2 text-body text-muted-foreground">
      AI 正在整理全班的觀點，請稍候…
    </p>
    <p v-if="generateError" role="alert" class="mt-2 text-body text-destructive">
      {{ generateError }}
    </p>

    <dl class="mt-4 grid gap-4 sm:grid-cols-3">
      <StatTile
        v-for="s in stats"
        :key="s.label"
        :label="s.label"
        :value="s.value"
        :icon="s.icon"
      />
    </dl>

    <TabNav v-model="tab" class="mt-4" :items="tabs" label="全班觀點分頁" />

    <section class="mt-4">
      <template v-if="tab === 'summary'">
        <QueryState
          :loading="summary.isPending.value"
          :error="summary.error.value"
          error-text="無法取得全班摘要"
          @retry="summary.refetch()"
        >
          <SummaryReviewTab
            v-if="summary.data.value?.summary"
            :topic-id="topicId"
            :data="summary.data.value"
            :can-edit="can('edit_summary')"
            :is-teacher="isTeacher"
          />
          <ComingSoon v-else title="還沒有全班摘要">
            學生完成探究之後，按「產生全班摘要」，AI 會依報告把全班的觀點分組整理。
          </ComingSoon>
        </QueryState>
      </template>
      <QueryState
        v-else
        :loading="reports.isPending.value"
        :error="reports.error.value"
        error-text="無法取得學生報告"
        @retry="reports.refetch()"
      >
        <StudentReportsTab
          v-if="reports.data.value"
          v-model:group="group"
          :data="reports.data.value"
        />
      </QueryState>
    </section>

    <ConfirmDialog
      v-model:open="generateOpen"
      title="產生全班摘要？"
      description="第一次產生摘要後，學生就不能再作答了（還沒完成的對話不會算進去），這個動作無法復原。"
      confirm-text="產生"
      :loading="generate.isPending.value"
      @confirm="generate.mutate()"
    />
  </div>
</template>
