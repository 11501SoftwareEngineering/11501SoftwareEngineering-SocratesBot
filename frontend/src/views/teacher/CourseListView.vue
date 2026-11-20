<script setup lang="ts">
import TextLink from '@/components/common/TextLink.vue'
/**
 * 老師：我的課程。對應 Figma「P09_Teacher_Home」（node 692:3019）、「P09_AddCourse」、
 * 「P09_Teacher_Home_Empty」（找不到課程）。
 * 左邊：課程卡（學生數、活動數；編輯、刪除）；右邊：AI 模型與用量。
 * 助教（學生帳號）也從這裡進教學端：只列被指派的課程，沒有新增／編輯／刪除與 AI 面板（照 Prototype）。
 * API：GET /courses、POST /courses、PUT /courses/{courseId}、DELETE /courses/{courseId}
 */
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { courseKeys, coursesApi, type CourseSummary } from '@/api/courses'
import AiUsagePanel from '@/components/ai/AiUsagePanel.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import QueryState from '@/components/common/QueryState.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import SectionHeading from '@/components/common/SectionHeading.vue'
import CourseCard from '@/components/course/CourseCard.vue'
import { AddRingIcon, EditIcon, TrashIcon } from '@/components/icons'
import CourseFormDialog from '@/components/teacher/CourseFormDialog.vue'
import { Button } from '@/components/ui/button'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useSearch } from '@/composables/useSearch'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const queryClient = useQueryClient()
const { data, isPending, error, refetch } = useQuery({
  queryKey: courseKeys.all,
  queryFn: coursesApi.list,
})
const authStore = useAuthStore()
const isTeacher = computed(() => authStore.hasRole('TEACHER'))
watch(data, (list) => list && authStore.syncTaAssignments(list))
// 教學端列自己教的課和當助教的課；學生身分的課程在「學生課程」
const courses = computed(() =>
  (data.value ?? []).filter((c) => c.my_role === 'teacher' || c.my_role === 'ta'),
)

const { keyword, results } = useSearch(
  () => courses.value,
  (c) => [c.name, c.invite_code, c.description ?? ''],
)

const formOpen = ref(false)
const editing = ref<CourseSummary | null>(null)
function openForm(course: CourseSummary | null) {
  editing.value = course
  formOpen.value = true
}

const remove = useConfirmAction((course: CourseSummary) => coursesApi.remove(course.course_id), {
  onSuccess: () => queryClient.invalidateQueries({ queryKey: courseKeys.all }),
  errorText: t('errors.deleteFailed'),
})
</script>

<template>
  <div
    class="mx-auto grid w-full max-w-[1200px] items-start gap-[38px] px-4 pt-[30px] pb-12"
    :class="isTeacher && 'lg:grid-cols-[minmax(0,731px)_minmax(0,398px)]'"
  >
    <section class="flex min-w-0 flex-col gap-2" aria-labelledby="courses-title">
      <SectionHeading :title="t('common.myCourses')" :count="courses.length" :level="1">
        <template #actions>
          <Button v-if="isTeacher" @click="openForm(null)"
            ><AddRingIcon /> {{ t('courses.addCourse') }}</Button
          >
        </template>
      </SectionHeading>
      <SearchInput v-model="keyword" :label="t('courses.search')" />
      <QueryState
        :loading="isPending"
        :error="error"
        :empty="results.length === 0"
        :empty-text="keyword || isTeacher ? t('courses.notFound') : t('courses.noAssigned')"
        :error-text="t('courses.loadError')"
        @retry="refetch()"
      >
        <template v-if="isTeacher" #empty-action>
          {{ t('common.tryPrefix')
          }}<TextLink inline @click="openForm(null)">{{ t('courses.addCourse') }}</TextLink>
        </template>
        <div class="flex flex-col gap-2">
          <CourseCard
            v-for="course in results"
            :key="course.course_id"
            :course="course"
            :to="{ name: 'TeacherCourse', params: { courseId: course.course_id } }"
          >
            <template v-if="course.my_role === 'teacher'" #actions>
              <Button
                variant="ghost"
                size="icon-sm"
                :aria-label="t('courses.editAria', { name: course.name })"
                @click="openForm(course)"
              >
                <EditIcon />
              </Button>
              <Button
                variant="ghost-danger"
                size="icon-sm"
                :aria-label="t('courses.deleteAria', { name: course.name })"
                @click="remove.ask(course)"
              >
                <TrashIcon />
              </Button>
            </template>
          </CourseCard>
        </div>
      </QueryState>
    </section>

    <AiUsagePanel v-if="isTeacher" />

    <CourseFormDialog v-model:open="formOpen" :course="editing" />
    <ConfirmDialog
      v-model:open="remove.open"
      :title="t('courses.deleteTitle')"
      :description="t('courses.deleteDescription', { name: remove.target?.name ?? '' })"
      :confirm-text="t('common.ok')"
      destructive
      :loading="remove.isPending"
      :error="remove.error"
      @confirm="remove.confirm()"
    />
  </div>
</template>
