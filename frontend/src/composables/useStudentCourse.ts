import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { studentApi } from '@/api/student'

// The page and header share the same server data through Vue Query.
export function useStudentCourse(courseId: MaybeRefOrGetter<string>) {
  const id = computed(() => toValue(courseId))

  return useQuery({
    queryKey: ['student', 'course', id],
    enabled: () => Boolean(id.value),
    queryFn: async ({ signal }) => {
      const { data } = await studentApi.getCourseTopics(id.value, signal)
      return data
    },
    retry: false,
  })
}
