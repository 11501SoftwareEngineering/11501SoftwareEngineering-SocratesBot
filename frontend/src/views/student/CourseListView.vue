<script setup lang="ts">
/**
 * 學生：我的課程。對應 Figma「Student_Home」（node 171:234）、「JoinCourse」。
 * API：GET /student/courses、POST /student/courses/join、DELETE /student/courses/{id}
 */
import { ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { studentApi, studentKeys, type Course } from '@/api/student'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import QueryState from '@/components/common/QueryState.vue'
import { AddRingIcon, SignOutIcon } from '@/components/icons'
import JoinCourseDialog from '@/components/student/JoinCourseDialog.vue'
import { Button } from '@/components/ui/button'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useSearch } from '@/composables/useSearch'

const queryClient = useQueryClient()
const { data, isPending, error, refetch } = useQuery({
  queryKey: studentKeys.courses,
  queryFn: studentApi.getCourses,
})
const { keyword, results } = useSearch(
  () => data.value ?? [],
  (c) => [c.name, c.invite_code, c.teacher_name],
)

const joinOpen = ref(false)
const notice = ref('')

const leave = useConfirmAction((course: Course) => studentApi.leaveCourse(course.course_id), {
  onSuccess: (course) => {
    notice.value = `已退出「${course.name}」`
    return queryClient.invalidateQueries({ queryKey: studentKeys.courses })
  },
  errorText: '退出失敗，請稍後再試',
})
</script>

<template>
  <div class="mx-auto w-full max-w-[960px] px-4 py-10 sm:py-12">
    <ListSection v-model:search="keyword" title="我的課程" search-label="搜尋課程">
      <template #actions>
        <Button @click="joinOpen = true">加入課程 <AddRingIcon /></Button>
      </template>

      <p v-if="notice" role="status" class="mb-3 rounded-lg bg-primary/30 px-4 py-2 text-body">
        {{ notice }}
      </p>

      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="
          keyword ? '找不到符合的課程' : '還沒有加入任何課程，請按「加入課程」輸入老師給的代碼'
        "
        error-text="無法取得課程列表"
        @retry="refetch()"
      >
        <ListCard
          v-for="course in results"
          :key="course.course_id"
          :title="course.name"
          :to="{ name: 'StudentCourse', params: { courseId: course.course_id } }"
        >
          <template #description>
            課程代碼: {{ course.invite_code }}
            <span v-if="course.teacher_name" class="ml-4">{{ course.teacher_name }}</span>
          </template>
          <template #actions>
            <Button
              variant="destructive"
              :aria-label="`退出 ${course.name}`"
              @click="leave.ask(course)"
            >
              <span class="hidden sm:inline">退出課程</span> <SignOutIcon />
            </Button>
          </template>
        </ListCard>
      </QueryState>
    </ListSection>

    <JoinCourseDialog v-model:open="joinOpen" @joined="(name) => (notice = `已加入「${name}」`)" />
    <ConfirmDialog
      v-model:open="leave.open"
      title="確認退出課程?"
      :description="`退出「${leave.target?.name}」後就不能再用課程代碼加入，要請老師把你加回來。`"
      confirm-text="確認"
      destructive
      :loading="leave.isPending"
      :error="leave.error"
      @confirm="leave.confirm()"
    />
  </div>
</template>
