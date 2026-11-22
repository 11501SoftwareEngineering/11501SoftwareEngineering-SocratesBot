<script setup lang="ts">
/**
 * 學生：探索結果報告。三個分頁：
 *   個人報告  Figma「P08_Student_Result_01」（node 787:3003）  GET /sessions/{sessionId}/report
 *   對話紀錄  Figma「P08_Student_Result_02」（node 785:4795）  GET /sessions/{sessionId}/messages
 *   全班摘要  Figma「P08_Student_Result_03」（node 787:2744）  GET /topics/{topicId}/summary/published
 *
 * 網址：/student/courses/:courseId/sessions/:sessionId/result/:tab（personal | chat | summary，沒寫就是 personal）
 * 題目名稱從課程的活動列表找（session_id 對得上的那一題）。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { sessionKeys, sessionsApi } from '@/api/sessions'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import TabNav from '@/components/common/TabNav.vue'
import { useCourseTopics } from '@/composables/useCourse'
import { pageClass } from '@/lib/ui'
import { useAuthStore } from '@/stores/auth'
import ChatRecordTab from './report/ChatRecordTab.vue'
import PersonalTab from './report/PersonalTab.vue'
import SummaryTab from './report/SummaryTab.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

type ReportTab = 'personal' | 'chat' | 'summary'

const route = useRoute()
const authStore = useAuthStore()
const courseId = computed(() => String(route.params.courseId ?? ''))
const sessionId = computed(() => String(route.params.sessionId ?? ''))
const currentTab = computed<ReportTab>(() => {
  const tab = route.params.tab
  return tab === 'chat' || tab === 'summary' ? tab : 'personal'
})

const { data: course } = useCourseTopics(courseId)
const topic = computed(() => course.value?.topics.find((t) => t.session_id === sessionId.value))

const tabs = computed(() =>
  (
    [
      { key: 'personal', label: t('report.personal') },
      { key: 'chat', label: t('report.chat') },
      { key: 'summary', label: t('report.summary') },
    ] as const
  ).map((tab) => ({
    ...tab,
    to: { name: 'StudentReport', params: { ...route.params, tab: tab.key } },
  })),
)

const messages = useQuery({
  queryKey: computed(() => sessionKeys.messages(sessionId.value)),
  queryFn: () => sessionsApi.messages(sessionId.value),
  enabled: () => currentTab.value === 'chat' && !!sessionId.value,
})
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      :title="t('report.title')"
      :breadcrumbs="[
        { label: t('common.myCourses'), to: { name: 'StudentCourses' } },
        {
          label: course?.name ?? t('common.course'),
          to: { name: 'StudentCourse', params: { courseId } },
        },
      ]"
    />

    <h2 class="mt-[23px] text-h1-title text-foreground">{{ topic?.title ?? '…' }}</h2>
    <TabNav class="mt-4" :items="tabs" :model-value="currentTab" :label="t('report.tabs')" />

    <section class="mt-4" :aria-label="tabs.find((t) => t.key === currentTab)?.label">
      <PersonalTab v-if="currentTab === 'personal'" :session-id="sessionId" />
      <QueryState
        v-else-if="currentTab === 'chat'"
        :loading="messages.isPending.value"
        :error="messages.error.value"
        :error-text="t('report.chatError')"
        @retry="messages.refetch()"
      >
        <ChatRecordTab
          :messages="messages.data.value?.messages ?? []"
          :student-name="authStore.user?.name"
        />
      </QueryState>
      <SummaryTab v-else :topic-id="topic?.topic_id ?? ''" />
    </section>
  </div>
</template>
