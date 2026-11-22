<script setup lang="ts">
/**
 * 學生：我的課程。對應 Figma「P05_Student_Home」（node 171:234）、「P05_JoinCourse」。
 * API：GET /courses、POST /courses/join、DELETE /courses/{courseId}/member（退出課程）
 *
 * 課程卡片兩欄排列。只列學生身分的課；當助教的課在教學端（頁首「我的課程」），照 Prototype。
 */
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { courseKeys, coursesApi, type CourseSummary } from '@/api/courses'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import QueryState from '@/components/common/QueryState.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import SectionHeading from '@/components/common/SectionHeading.vue'
import CourseCard from '@/components/course/CourseCard.vue'
import { AddRingIcon, LeaveIcon } from '@/components/icons'
import JoinCourseDialog from '@/components/student/JoinCourseDialog.vue'
import { Button } from '@/components/ui/button'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useSearch } from '@/composables/useSearch'
import { pageClass } from '@/lib/ui'
import { useAuthStore } from '@/stores/auth'

const queryClient = useQueryClient()
const { data, isPending, error, refetch } = useQuery({
  queryKey: courseKeys.all,
  queryFn: coursesApi.list,
})

const authStore = useAuthStore()
watch(data, (list) => list && authStore.syncTaAssignments(list))
const courses = computed(() => (data.value ?? []).filter((c) => c.my_role === 'student'))

const { keyword, results } = useSearch(
  () => courses.value,
  (c) => [c.name, c.invite_code, c.description ?? '', c.teacher_name],
)

const joinOpen = ref(false)
const notice = ref('')

const leave = useConfirmAction((course: CourseSummary) => coursesApi.leave(course.course_id), {
  onSuccess: () => queryClient.invalidateQueries({ queryKey: courseKeys.all }),
  errorText: '退出失敗，請稍後再試',
})
</script>

<template>
  <div :class="pageClass">
    <SectionHeading title="我的課程" :count="courses.length" :level="1">
      <template #actions>
        <Button @click="joinOpen = true"><AddRingIcon /> 加入課程</Button>
      </template>
    </SectionHeading>
    <p v-if="notice" role="status" class="mt-2 text-body-lg text-foreground">{{ notice }}</p>
    <SearchInput v-model="keyword" label="搜尋課程" class="mt-2" />

    <QueryState
      class="mt-2"
      :loading="isPending"
      :error="error"
      :empty="results.length === 0"
      empty-text="找不到課程"
      error-text="無法取得課程列表"
      @retry="refetch()"
    >
      <template #empty-action>
        試試<button
          type="button"
          class="rounded underline underline-offset-4 outline-none hover:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          @click="joinOpen = true"
        >
          加入課程
        </button>
      </template>
      <div class="grid gap-4 md:grid-cols-2">
        <CourseCard
          v-for="course in results"
          :key="course.course_id"
          :course="course"
          :to="{ name: 'StudentCourse', params: { courseId: course.course_id } }"
          show-teacher
        >
          <template #actions>
            <Button
              variant="ghost"
              size="icon-sm"
              :aria-label="`退出課程 ${course.name}`"
              @click="leave.ask(course)"
            >
              <LeaveIcon />
            </Button>
          </template>
        </CourseCard>
      </div>
    </QueryState>

    <JoinCourseDialog v-model:open="joinOpen" @joined="(name) => (notice = `已加入「${name}」`)" />
    <ConfirmDialog
      v-model:open="leave.open"
      title="退出課程？"
      :description="`退出「${leave.target?.name}」之後就看不到這門課了，要再加入請重新輸入課程代碼。`"
      confirm-text="退出"
      destructive
      :loading="leave.isPending"
      :error="leave.error"
      @confirm="leave.confirm()"
    />
  </div>
</template>
