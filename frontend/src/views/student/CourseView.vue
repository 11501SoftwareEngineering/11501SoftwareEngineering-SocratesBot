<script setup lang="ts">
/**
 * 學生：課程裡的問題列表。對應 Figma「Student_Course」（node 171:257）。
 * API：GET /student/courses/{courseId}/topics
 * 點問題：還沒完成 → 對話頁；已完成 → 結果頁
 */
import { computed } from 'vue'
import { useRoute, type RouteLocationRaw } from 'vue-router'
import type { SessionStatus, Topic } from '@/api/student'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import QueryState from '@/components/common/QueryState.vue'
import { features } from '@/config/features'
import { useStudentCourse } from '@/composables/useCourseDetail'
import { useSearch } from '@/composables/useSearch'

const route = useRoute()
const courseId = computed(() => String(route.params.courseId ?? ''))
const { data: course, isPending, error, refetch } = useStudentCourse(courseId)
const { keyword, results } = useSearch(
  () => course.value?.topics ?? [],
  (t) => [t.title, t.description],
)

// 後端回傳 null 代表還沒開始，不顯示標籤
const STATUS_LABEL: Record<SessionStatus, string> = {
  IN_PROGRESS: '進行中',
  COMPLETED: '已完成',
}

function topicLink(topic: Topic): RouteLocationRaw {
  if (topic.status === 'COMPLETED' && topic.session_id) {
    return {
      name: 'StudentResult',
      params: { courseId: courseId.value, sessionId: topic.session_id },
    }
  }
  return { name: 'StudentChat', params: { courseId: courseId.value, topicId: topic.topic_id } }
}
</script>

<template>
  <div class="mx-auto w-full max-w-[960px] px-4 py-10 sm:py-12">
    <ListSection v-model:search="keyword" title="問題列表" search-label="搜尋問題">
      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="keyword ? '找不到符合的問題' : '老師還沒有出題目，晚點再來看看'"
        error-text="無法取得問題列表"
        @retry="refetch()"
      >
        <ListCard
          v-for="topic in results"
          :key="topic.topic_id"
          :title="topic.title"
          :to="topicLink(topic)"
        >
          <template v-if="features.topicSettings" #description>
            <span class="mr-4">年齡層：{{ topic.age_range ?? '未提供' }}</span>
            <span class="mr-4">回合數：{{ topic.max_rounds ?? '未提供' }}</span>
          </template>
          <template v-else-if="topic.description" #description>{{ topic.description }}</template>
          <template v-if="topic.status" #actions>
            <span
              class="rounded-lg px-3 py-1 text-body"
              :class="
                topic.status === 'COMPLETED'
                  ? 'bg-primary/40 text-foreground'
                  : 'bg-secondary/70 text-foreground'
              "
            >
              {{ STATUS_LABEL[topic.status] }}
            </span>
          </template>
        </ListCard>
      </QueryState>
    </ListSection>
  </div>
</template>
