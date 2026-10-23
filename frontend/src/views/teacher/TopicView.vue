<script setup lang="ts">
/**
 * 老師：單一問題的結果。對應 Figma「Teacher_Question」（node 171:211）、「AddResult」。
 *   左邊「結果列表」：各結論人數，點開看是哪些學生；可以新增、刪除結論
 *   右邊「學生列表」：全班學生的完成狀態；可以把學生移出課程
 * API：GET /teacher/topics/{id}/conclusions、GET /teacher/topics/{id}/analytics、
 *      GET /teacher/courses/{id}/students、POST/DELETE 結論、DELETE 學生
 */
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { teacherApi, teacherKeys, type Conclusion, type CourseStudent } from '@/api/teacher'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import QueryState from '@/components/common/QueryState.vue'
import { AddRingIcon, TrashIcon } from '@/components/icons'
import ConclusionFormDialog from '@/components/teacher/ConclusionFormDialog.vue'
import { Button } from '@/components/ui/button'
import { useTeacherCourse } from '@/composables/useCourseDetail'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useSearch } from '@/composables/useSearch'

const route = useRoute()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const topicId = computed(() => String(route.params.topicId ?? ''))

const { data: course } = useTeacherCourse(courseId)
const topic = computed(() => course.value?.topics.find((t) => t.topic_id === topicId.value))

const conclusionsQuery = useQuery({
  queryKey: computed(() => teacherKeys.conclusions(topicId.value)),
  queryFn: () => teacherApi.getConclusions(topicId.value),
})
const analyticsQuery = useQuery({
  queryKey: computed(() => teacherKeys.analytics(topicId.value)),
  queryFn: () => teacherApi.getTopicAnalytics(topicId.value),
})
const studentsQuery = useQuery({
  queryKey: computed(() => teacherKeys.students(courseId.value)),
  queryFn: () => teacherApi.getCourseStudents(courseId.value),
})

// ----- 結果列表 -----
const conclusionSearch = useSearch(
  () => conclusionsQuery.data.value?.conclusions ?? [],
  (k) => [k.title, k.description, ...k.students.map((s) => s.display_name)],
)
const expanded = reactive<Record<string, boolean>>({})
const conclusionFormOpen = ref(false)

const studentTotal = computed(() => studentsQuery.data.value?.length)
const answered = computed(() => conclusionsQuery.data.value?.total_answered ?? 0)

const removeConclusion = useConfirmAction(
  (k: Conclusion) => teacherApi.deleteConclusion(topicId.value, k.conclusion_id),
  {
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: teacherKeys.conclusions(topicId.value) })
      void queryClient.invalidateQueries({ queryKey: teacherKeys.analytics(topicId.value) })
    },
  },
)

// ----- 學生列表 -----
const statusByStudent = computed(() => {
  const map = new Map<string, string>()
  for (const arg of analyticsQuery.data.value?.arguments ?? []) {
    map.set(arg.student_id, arg.conclusion_title ? `已完成（${arg.conclusion_title}）` : '已完成')
  }
  return map
})
const studentSearch = useSearch(
  () => studentsQuery.data.value ?? [],
  (s) => [s.name, s.account, statusByStudent.value.get(s.student_id) ?? '未完成'],
)

const removeStudent = useConfirmAction(
  (s: CourseStudent) => teacherApi.removeStudent(courseId.value, s.student_id),
  {
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['teacher'] }),
  },
)
</script>

<template>
  <div class="mx-auto w-full max-w-[1100px] px-4 py-10 sm:py-12">
    <h1 class="mb-6 text-h2-title leading-normal text-muted-foreground">
      問題：<span class="text-foreground">{{ topic?.title ?? '…' }}</span>
    </h1>

    <div class="grid gap-12 lg:grid-cols-2 lg:gap-16">
      <ListSection
        v-model:search="conclusionSearch.keyword.value"
        title="結果列表"
        :level="2"
        search-label="搜尋結論"
      >
        <template #toolbar>
          <div class="flex flex-wrap items-center gap-4">
            <p
              class="rounded-2xl bg-muted px-4 py-3 text-h2-title text-foreground shadow-elevated"
              aria-live="polite"
            >
              總完成人數：{{ answered }}/{{ studentTotal ?? '–' }}
            </p>
            <Button @click="conclusionFormOpen = true">新增結論 <AddRingIcon /></Button>
          </div>
        </template>

        <QueryState
          :loading="conclusionsQuery.isPending.value"
          :error="conclusionsQuery.error.value"
          :empty="conclusionSearch.results.value.length === 0"
          :empty-text="
            conclusionSearch.keyword.value ? '找不到符合的結論' : '還沒有結論，按「新增結論」建立'
          "
          :skeleton-count="2"
          @retry="conclusionsQuery.refetch()"
        >
          <ListCard
            v-for="k in conclusionSearch.results.value"
            :key="k.conclusion_id"
            v-model:expanded="expanded[k.conclusion_id]"
            :title="k.title"
            :description="`人數：${k.count}（${k.percentage}%）`"
            :expandable="k.students.length > 0"
          >
            <template #details>
              <p v-if="k.description" class="mb-1 text-body">{{ k.description }}</p>
              <ul class="text-body">
                <li v-for="s in k.students" :key="s.student_id">{{ s.display_name }}</li>
              </ul>
            </template>
            <template #actions>
              <Button
                variant="destructive"
                :aria-label="`刪除結論 ${k.title}`"
                @click="removeConclusion.ask(k)"
              >
                <span class="hidden sm:inline">刪除</span> <TrashIcon />
              </Button>
            </template>
          </ListCard>
        </QueryState>
      </ListSection>

      <ListSection
        v-model:search="studentSearch.keyword.value"
        title="學生列表"
        :level="2"
        search-label="搜尋學生"
      >
        <QueryState
          :loading="studentsQuery.isPending.value"
          :error="studentsQuery.error.value"
          :empty="studentSearch.results.value.length === 0"
          :empty-text="
            studentSearch.keyword.value ? '找不到符合的學生' : '還沒有學生加入，請把課程代碼給學生'
          "
          @retry="studentsQuery.refetch()"
        >
          <ListCard
            v-for="s in studentSearch.results.value"
            :key="s.student_id"
            :title="s.name"
            :description="`狀態：${statusByStudent.get(s.student_id) ?? '未完成'}`"
          >
            <template #actions>
              <Button
                variant="destructive"
                :aria-label="`把 ${s.name} 移出課程`"
                @click="removeStudent.ask(s)"
              >
                <span class="hidden sm:inline">刪除</span> <TrashIcon />
              </Button>
            </template>
          </ListCard>
        </QueryState>
      </ListSection>
    </div>

    <ConclusionFormDialog v-model:open="conclusionFormOpen" :topic-id="topicId" />
    <ConfirmDialog
      v-model:open="removeConclusion.open"
      title="確認刪除?"
      :description="`刪除結論「${removeConclusion.target?.title}」後，原本歸在這裡的學生會變成未分類。`"
      confirm-text="確認"
      destructive
      :loading="removeConclusion.isPending"
      :error="removeConclusion.error"
      @confirm="removeConclusion.confirm()"
    />
    <ConfirmDialog
      v-model:open="removeStudent.open"
      title="確認移出課程?"
      :description="`「${removeStudent.target?.name}」會被移出「${course?.name ?? '這門課'}」，他在這門課的作答紀錄也會刪除。`"
      confirm-text="確認"
      destructive
      :loading="removeStudent.isPending"
      :error="removeStudent.error"
      @confirm="removeStudent.confirm()"
    />
  </div>
</template>
