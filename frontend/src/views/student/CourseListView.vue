<script setup lang="ts">
import TextLink from '@/components/common/TextLink.vue'
import AppBanner from '@/components/common/AppBanner.vue'
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
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

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
  errorText: t('courses.leaveFailed'),
})
</script>

<template>
  <div :class="pageClass">
    <SectionHeading :title="t('common.myCourses')" :count="courses.length" :level="1">
      <template #actions>
        <Button @click="joinOpen = true"><AddRingIcon /> {{ t('courses.join') }}</Button>
      </template>
    </SectionHeading>
    <AppBanner v-if="notice" type="success" class="mt-2">{{ notice }}</AppBanner>
    <SearchInput v-model="keyword" :label="t('courses.search')" class="mt-2" />

    <QueryState
      class="mt-2"
      :loading="isPending"
      :error="error"
      :empty="results.length === 0"
      :empty-text="t('courses.notFound')"
      :error-text="t('courses.loadError')"
      @retry="refetch()"
    >
      <template #empty-action>
        {{ t('common.tryPrefix')
        }}<TextLink inline @click="joinOpen = true">{{ t('courses.join') }}</TextLink>
      </template>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <CourseCard
          v-for="course in results"
          :key="course.course_id"
          :course="course"
          :to="{ name: 'StudentCourse', params: { courseId: course.course_id } }"
          show-teacher
        >
          <template #actions>
            <Button
              variant="ghost-danger"
              size="icon-sm"
              :aria-label="t('courses.leaveAria', { name: course.name })"
              @click="leave.ask(course)"
            >
              <LeaveIcon />
            </Button>
          </template>
        </CourseCard>
      </div>
    </QueryState>

    <JoinCourseDialog
      v-model:open="joinOpen"
      @joined="(name) => (notice = t('courses.joined', { name }))"
    />
    <ConfirmDialog
      v-model:open="leave.open"
      :title="t('courses.leaveTitle')"
      :description="t('courses.leaveDescription', { name: leave.target?.name ?? '' })"
      :confirm-text="t('courses.leave')"
      destructive
      :loading="leave.isPending"
      :error="leave.error"
      @confirm="leave.confirm()"
    />
  </div>
</template>
