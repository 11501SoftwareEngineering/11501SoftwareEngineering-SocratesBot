import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { courseKeys, coursesApi } from '@/api/courses'

/** 課程基本資訊（GET /courses/{courseId}）：麵包屑、標題、課程描述 */
export function useCourse(courseId: MaybeRefOrGetter<string>) {
  const id = computed(() => toValue(courseId))
  return useQuery({
    queryKey: computed(() => courseKeys.detail(id.value)),
    enabled: () => Boolean(id.value),
    queryFn: () => coursesApi.get(id.value),
    retry: false,
  })
}

/** 課程的探究活動列表（GET /courses/{courseId}/topics）；同一頁多個地方用，只會打一次 API */
export function useCourseTopics(courseId: MaybeRefOrGetter<string>) {
  const id = computed(() => toValue(courseId))
  return useQuery({
    queryKey: computed(() => courseKeys.topics(id.value)),
    enabled: () => Boolean(id.value),
    queryFn: () => coursesApi.topics(id.value),
    retry: false,
  })
}
