import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { teacherApi, teacherKeys } from '@/api/teacher'

/**
 * 老師舊版課程頁用的課程資訊＋問題列表（v0.2 頁面改用 composables/useCourse.ts）。
 */
export function useTeacherCourse(courseId: MaybeRefOrGetter<string>) {
  const id = computed(() => toValue(courseId))
  return useQuery({
    queryKey: computed(() => teacherKeys.course(id.value)),
    enabled: () => Boolean(id.value),
    queryFn: () => teacherApi.getCourseTopics(id.value),
    retry: false,
  })
}
