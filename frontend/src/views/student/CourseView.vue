<script setup lang="ts">
/**
 * 學生：課程頁（探究活動列表）。對應 Figma「P06_Student_Course」（node 171:257）。
 * API：GET /courses/{courseId}（課程描述）、GET /courses/{courseId}/topics
 *
 * 活動卡片的狀態和連結：
 *   還沒開始 → 尚未開始、「開始探究 →」
 *   進行中   → 進行中、「繼續探究 →」
 *   已完成   → 已完成、「檢視個人報告 →」
 *   老師已經在整理摘要（topic_status = summary）、自己沒做完 → 已結束，不能再作答
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { TopicListItem } from '@/api/courses'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import SectionHeading from '@/components/common/SectionHeading.vue'
import ActivityCard from '@/components/course/ActivityCard.vue'
import { useCourse, useCourseTopics } from '@/composables/useCourse'
import { useSearch } from '@/composables/useSearch'
import { pageClass } from '@/lib/ui'

const route = useRoute()
const courseId = computed(() => String(route.params.courseId ?? ''))
const { data: course } = useCourse(courseId)
const { data, isPending, error, refetch } = useCourseTopics(courseId)

const { keyword, results } = useSearch(
  () => data.value?.topics ?? [],
  (t) => [t.title, t.description ?? ''],
)

function cardFor(topic: TopicListItem) {
  const chat = {
    name: 'StudentChat',
    params: { courseId: courseId.value, topicId: topic.topic_id },
  }
  if (topic.session_status === 'COMPLETED' && topic.session_id) {
    return {
      status: { label: '已完成', tone: 'primary' as const },
      link: {
        label: '檢視個人報告',
        arrow: '→' as const,
        to: {
          name: 'StudentReport',
          params: { courseId: courseId.value, sessionId: topic.session_id, tab: 'personal' },
        },
      },
    }
  }
  if (topic.topic_status === 'summary') {
    return { status: { label: '已結束', tone: 'secondary' as const }, link: undefined }
  }
  if (topic.session_status === 'IN_PROGRESS') {
    return {
      status: { label: '進行中', tone: 'secondary' as const },
      link: { label: '繼續探究', arrow: '→' as const, to: chat },
    }
  }
  return {
    status: { label: '尚未開始', tone: 'secondary' as const },
    link: { label: '開始探究', arrow: '→' as const, to: chat },
  }
}
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      :title="course?.name ?? data?.name ?? '課程'"
      :breadcrumbs="[{ label: '我的課程', to: { name: 'StudentCourses' } }]"
      :description="course?.description"
    />

    <section class="mt-4 flex flex-col gap-2">
      <SectionHeading title="探究活動" :count="data?.topics.length ?? 0" />
      <SearchInput v-model="keyword" label="搜尋探究活動" />
      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="keyword ? '找不到探究活動' : '還沒有探究活動'"
        error-text="無法取得探究活動"
        @retry="refetch()"
      >
        <div class="grid gap-4 md:grid-cols-2">
          <ActivityCard
            v-for="topic in results"
            :key="topic.topic_id"
            :title="topic.title"
            :description="topic.description"
            :max-turns="topic.max_turns"
            v-bind="cardFor(topic)"
          />
        </div>
      </QueryState>
    </section>
  </div>
</template>
