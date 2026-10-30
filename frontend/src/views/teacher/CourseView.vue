<script setup lang="ts">
/**
 * 老師：課程裡的問題列表。對應 Figma「Teacher_Course」（node 171:188）、「AddQuistion」。
 * API：GET /teacher/courses/{id}/topics、GET /teacher/courses/{id}/students（算已完成人數 X/全班）
 *      POST/PUT/DELETE /teacher/topics
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { teacherApi, teacherKeys, type TeacherTopic } from '@/api/teacher'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import QueryState from '@/components/common/QueryState.vue'
import { AddRingIcon, EditIcon, TrashIcon } from '@/components/icons'
import TopicFormDialog from '@/components/teacher/TopicFormDialog.vue'
import { Button } from '@/components/ui/button'
import { features } from '@/config/features'
import { useTeacherCourse } from '@/composables/useCourseDetail'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useSearch } from '@/composables/useSearch'

const route = useRoute()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))

const { data: course, isPending, error, refetch } = useTeacherCourse(courseId)
const { data: students } = useQuery({
  queryKey: computed(() => teacherKeys.students(courseId.value)),
  queryFn: () => teacherApi.getCourseStudents(courseId.value),
})
const { keyword, results } = useSearch(
  () => course.value?.topics ?? [],
  (t) => [t.title, t.description],
)

const formOpen = ref(false)
const editing = ref<TeacherTopic | null>(null)
function openForm(topic: TeacherTopic | null) {
  editing.value = topic
  formOpen.value = true
}

const remove = useConfirmAction((topic: TeacherTopic) => teacherApi.deleteTopic(topic.topic_id), {
  onSuccess: () => queryClient.invalidateQueries({ queryKey: teacherKeys.course(courseId.value) }),
  errorText: '刪除失敗，請稍後再試',
})

const studentTotal = computed(() => (students.value ? String(students.value.length) : '–'))
</script>

<template>
  <div class="mx-auto w-full max-w-[960px] px-4 py-10 sm:py-12">
    <p v-if="course" class="mb-1 text-body-lg text-muted-foreground">
      {{ course.name }}・課程代碼
      <span class="font-bold text-foreground">{{ course.invite_code }}</span>
    </p>
    <ListSection v-model:search="keyword" title="問題列表" search-label="搜尋問題">
      <template #actions>
        <Button :disabled="!course" @click="openForm(null)">新增問題 <AddRingIcon /></Button>
      </template>

      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="keyword ? '找不到符合的問題' : '這門課還沒有問題，按「新增問題」出第一題'"
        error-text="無法取得問題列表"
        @retry="refetch()"
      >
        <ListCard
          v-for="topic in results"
          :key="topic.topic_id"
          :title="topic.title"
          :to="{ name: 'TeacherTopic', params: { courseId, topicId: topic.topic_id } }"
        >
          <template #description>
            <template v-if="features.topicSettings">
              <span class="mr-4">年齡層：{{ topic.age_range ?? '未設定' }}</span>
              <span class="mr-4">回合數：{{ topic.max_rounds ?? '未設定' }}</span>
            </template>
            <span>已完成人數：{{ topic.answered_count }}/{{ studentTotal }}</span>
          </template>
          <template #actions>
            <Button
              variant="secondary"
              :aria-label="`編輯 ${topic.title}`"
              @click="openForm(topic)"
            >
              <span class="hidden sm:inline">編輯</span> <EditIcon />
            </Button>
            <Button
              variant="destructive"
              :aria-label="`刪除 ${topic.title}`"
              @click="remove.ask(topic)"
            >
              <span class="hidden sm:inline">刪除</span> <TrashIcon />
            </Button>
          </template>
        </ListCard>
      </QueryState>
    </ListSection>

    <TopicFormDialog v-model:open="formOpen" :course-id="courseId" :topic="editing" />
    <ConfirmDialog
      v-model:open="remove.open"
      title="確認刪除?"
      :description="`刪除「${remove.target?.title}」後，學生的對話和結論都會一起刪除，這個動作無法復原。`"
      confirm-text="確認"
      destructive
      :loading="remove.isPending"
      :error="remove.error"
      @confirm="remove.confirm()"
    />
  </div>
</template>
