<script setup lang="ts">
/**
 * 學生：探索結果報告。有三個分頁：
 *   個人報告  Figma「Student_Result_01」（node 787:3003）⚠️ 還沒做
 *   對話紀錄  Figma「Student_Result_02」（node 785:4795）
 *   全班摘要  Figma「Student_Result_03」（node 787:2744）⚠️ 還沒做
 *
 * 網址：/student/courses/:courseId/sessions/:sessionId/report/:tab
 *   tab = personal | chat | summary，沒寫就是 personal
 *
 * ⚠️ 還沒接 API，資料來自 src/data/sampleReport.ts。之後要接的 API（docs/API功能規格.md v0.2）：
 *   對話紀錄 GET /sessions/{sessionId}/messages
 *   個人報告 GET /sessions/{sessionId}/report
 *   全班摘要 GET /topics/{topicId}/summary/published
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PageBreadcrumbs from '@/components/common/PageBreadcrumbs.vue'
import ComingSoon from '@/components/common/ComingSoon.vue'
import { sampleReport } from '@/data/sampleReport'
import { useAuthStore } from '@/stores/auth'
import ChatRecordTab from './report/ChatRecordTab.vue'

type ReportTab = 'personal' | 'chat' | 'summary'

const route = useRoute()
const authStore = useAuthStore()

const report = sampleReport
const tabs: { key: ReportTab; label: string }[] = [
  { key: 'personal', label: '個人報告' },
  { key: 'chat', label: '對話紀錄' },
  { key: 'summary', label: '全班摘要' },
]
const currentTab = computed<ReportTab>(() => {
  const tab = route.params.tab
  return tab === 'chat' || tab === 'summary' ? tab : 'personal'
})
const comingSoon: Record<Exclude<ReportTab, 'chat'>, string> = {
  personal: '個人報告',
  summary: '全班摘要',
}

const courseId = computed(() => String(route.params.courseId ?? report.course_id))
const breadcrumbs = computed(() => [
  { label: '我的課程', to: { name: 'StudentCourses' } },
  {
    label: report.course_name,
    to: { name: 'StudentCourse', params: { courseId: courseId.value } },
  },
])
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pt-[30px] pb-12">
    <header class="flex flex-col gap-2">
      <PageBreadcrumbs :items="breadcrumbs" />
      <h1 class="text-page-title text-foreground">探索結果報告</h1>
    </header>

    <h2 class="mt-[23px] text-h1-title text-foreground">{{ report.topic_title }}</h2>

    <nav class="mt-4" aria-label="報告分頁">
      <ul class="flex border-b-2 border-foreground px-1">
        <li v-for="tab in tabs" :key="tab.key">
          <RouterLink
            :to="{ name: 'StudentReport', params: { ...route.params, tab: tab.key } }"
            class="relative block rounded-t px-3 pb-4 text-header outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            :class="
              tab.key === currentTab
                ? 'text-foreground after:absolute after:inset-x-0 after:-bottom-1 after:h-1.5 after:bg-foreground'
                : 'text-muted-foreground hover:text-foreground'
            "
            :aria-current="tab.key === currentTab ? 'page' : undefined"
            >{{ tab.label }}</RouterLink
          >
        </li>
      </ul>
    </nav>

    <section class="mt-4" :aria-label="tabs.find((t) => t.key === currentTab)?.label">
      <ChatRecordTab
        v-if="currentTab === 'chat'"
        :messages="report.messages"
        :student-name="authStore.user?.name"
      />
      <ComingSoon v-else :title="`${comingSoon[currentTab]}製作中`">
        這個分頁還在開發，先看看「對話紀錄」。
      </ComingSoon>
    </section>
  </div>
</template>
