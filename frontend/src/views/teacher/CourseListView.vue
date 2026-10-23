<script setup lang="ts">
/**
 * 老師：我的課程。對應 Figma「Teacher_Home」（node 171:165）、「AddCourse」。
 * API：GET/POST /teacher/courses、⚠️ PUT /teacher/courses/{id}、DELETE /teacher/courses/{id}
 */
import { ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { teacherApi, teacherKeys, type TeacherCourse } from '@/api/teacher'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import QueryState from '@/components/common/QueryState.vue'
import { AddRingIcon, EditIcon, TrashIcon } from '@/components/icons'
import CourseFormDialog from '@/components/teacher/CourseFormDialog.vue'
import { Button } from '@/components/ui/button'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useSearch } from '@/composables/useSearch'

const queryClient = useQueryClient()
const { data, isPending, error, refetch } = useQuery({
  queryKey: teacherKeys.courses,
  queryFn: teacherApi.getCourses,
})
const { keyword, results } = useSearch(
  () => data.value ?? [],
  (c) => [c.name, c.invite_code, c.description],
)

const formOpen = ref(false)
const editing = ref<TeacherCourse | null>(null)
function openForm(course: TeacherCourse | null) {
  editing.value = course
  formOpen.value = true
}

const remove = useConfirmAction(
  (course: TeacherCourse) => teacherApi.deleteCourse(course.course_id),
  {
    onSuccess: () => queryClient.invalidateQueries({ queryKey: teacherKeys.courses }),
    errorText: '刪除失敗，請稍後再試',
  },
)
</script>

<template>
  <div class="mx-auto w-full max-w-[960px] px-4 py-10 sm:py-12">
    <ListSection v-model:search="keyword" title="我的課程" search-label="搜尋課程">
      <template #actions>
        <Button @click="openForm(null)">新增課程 <AddRingIcon /></Button>
      </template>

      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="keyword ? '找不到符合的課程' : '還沒有課程，按「新增課程」建立第一門課'"
        error-text="無法取得課程列表"
        @retry="refetch()"
      >
        <ListCard
          v-for="course in results"
          :key="course.course_id"
          :title="course.name"
          :to="{ name: 'TeacherCourse', params: { courseId: course.course_id } }"
        >
          <template #description>
            課程代碼: {{ course.invite_code }}
            <span class="ml-4">學生 {{ course.student_count }} 人</span>
          </template>
          <template #actions>
            <Button
              variant="secondary"
              :aria-label="`編輯 ${course.name}`"
              @click="openForm(course)"
            >
              <span class="hidden sm:inline">編輯</span> <EditIcon />
            </Button>
            <Button
              variant="destructive"
              :aria-label="`刪除 ${course.name}`"
              @click="remove.ask(course)"
            >
              <span class="hidden sm:inline">刪除課程</span> <TrashIcon />
            </Button>
          </template>
        </ListCard>
      </QueryState>
    </ListSection>

    <CourseFormDialog v-model:open="formOpen" :course="editing" />
    <ConfirmDialog
      v-model:open="remove.open"
      title="確認刪除?"
      :description="`刪除「${remove.target?.name}」後，課程裡的問題和學生的作答紀錄都會一起刪除，這個動作無法復原。`"
      confirm-text="確認"
      destructive
      :loading="remove.isPending"
      :error="remove.error"
      @confirm="remove.confirm()"
    />
  </div>
</template>
