<script setup lang="ts">
/**
 * 學生：對話結果。對應 Figma「Student_Question_Result」（node 354:2234）。
 *   左邊：這次的對話紀錄
 *   右邊「結果列表」：全班各結論人數，自己的結論會標起來；可以切換「匿名」
 * API：GET /student/sessions/{id}/result、GET /student/topics/{id}/analytics、
 *      PATCH /student/sessions/{id}/privacy、⚠️ GET /student/sessions/{id}/messages
 */
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { studentApi, studentKeys } from '@/api/student'
import AppCheckbox from '@/components/common/AppCheckbox.vue'
import ChatBubble from '@/components/common/ChatBubble.vue'
import ListCard from '@/components/common/ListCard.vue'
import ListSection from '@/components/common/ListSection.vue'
import QueryState from '@/components/common/QueryState.vue'
import { useStudentCourse } from '@/composables/useCourseDetail'
import { useSearch } from '@/composables/useSearch'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const sessionId = computed(() => String(route.params.sessionId ?? ''))

const resultQuery = useQuery({
  queryKey: computed(() => studentKeys.result(sessionId.value)),
  queryFn: () => studentApi.getSessionResult(sessionId.value),
  retry: false,
})
const topicId = computed(() => resultQuery.data.value?.topic_id ?? '')

const analyticsQuery = useQuery({
  queryKey: computed(() => studentKeys.analytics(topicId.value)),
  queryFn: () => studentApi.getTopicAnalytics(topicId.value),
  enabled: () => !!topicId.value,
})
const messagesQuery = useQuery({
  queryKey: computed(() => studentKeys.messages(sessionId.value)),
  queryFn: () => studentApi.getSessionMessages(sessionId.value),
})

const { data: course } = useStudentCourse(courseId)
const topic = computed(() => course.value?.topics.find((t) => t.topic_id === topicId.value))

const { keyword, results } = useSearch(
  () => analyticsQuery.data.value?.conclusions ?? [],
  (k) => [k.title, ...k.students.map((s) => s.display_name)],
)
const expanded = reactive<Record<string, boolean>>({})

// ----- 匿名設定 -----
const isAnonymous = ref(false)
const privacyError = ref('')
watch(
  () => resultQuery.data.value?.is_anonymous,
  (value) => (isAnonymous.value = !!value),
  { immediate: true },
)
const privacyMutation = useMutation({
  mutationFn: (value: boolean) => studentApi.updatePrivacy(sessionId.value, value),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: studentKeys.result(sessionId.value) })
    void queryClient.invalidateQueries({ queryKey: studentKeys.analytics(topicId.value) })
  },
  onError: (err, value) => {
    isAnonymous.value = !value
    privacyError.value = getApiErrorMessage(err, '匿名設定沒有儲存成功')
  },
})
function handlePrivacy(value: boolean) {
  privacyError.value = ''
  isAnonymous.value = value
  privacyMutation.mutate(value)
}

const myConclusionId = computed(() => resultQuery.data.value?.conclusion_id)
const studentName = computed(() => authStore.user?.name ?? '學生')
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 py-10 sm:py-12">
    <QueryState
      :loading="resultQuery.isPending.value"
      :error="resultQuery.error.value"
      error-text="無法取得結果"
      :skeleton-count="2"
      @retry="resultQuery.refetch()"
    >
      <div class="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.75fr)] lg:gap-16">
        <section aria-labelledby="result-topic">
          <h1 id="result-topic" class="mb-6 text-h1-title text-foreground">
            {{ topic?.title ?? '對話紀錄' }}
          </h1>
          <p
            v-if="resultQuery.data.value?.conclusion_title"
            class="mb-6 rounded-2xl bg-primary/30 px-4 py-3 text-body-lg text-foreground"
          >
            你的結論：<strong>{{ resultQuery.data.value.conclusion_title }}</strong>
          </p>
          <QueryState
            :loading="messagesQuery.isPending.value"
            :error="messagesQuery.error.value"
            error-text="無法取得對話紀錄"
            :skeleton-count="2"
            @retry="messagesQuery.refetch()"
          >
            <ol class="flex flex-col gap-6" aria-label="對話紀錄">
              <li
                v-for="message in messagesQuery.data.value?.messages ?? []"
                :key="message.message_id"
                class="flex"
                :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
              >
                <ChatBubble
                  :from="message.role === 'user' ? 'student' : 'ai'"
                  :name="message.role === 'user' ? studentName : undefined"
                  >{{ message.content }}</ChatBubble
                >
              </li>
            </ol>
          </QueryState>
        </section>

        <ListSection v-model:search="keyword" title="結果列表" :level="2" search-label="搜尋結論">
          <template #heading>
            <AppCheckbox
              :model-value="isAnonymous"
              :disabled="privacyMutation.isPending.value"
              @update:model-value="handlePrivacy"
              >匿名</AppCheckbox
            >
          </template>
          <p v-if="privacyError" role="alert" class="mb-2 text-right text-body text-destructive">
            {{ privacyError }}
          </p>
          <p class="mb-3 text-body text-muted-foreground">
            勾選「匿名」後，其他同學看到的會是「匿名同學」。共
            {{ analyticsQuery.data.value?.total_answered ?? 0 }} 人完成。
          </p>
          <QueryState
            :loading="analyticsQuery.isPending.value"
            :error="analyticsQuery.error.value"
            :empty="results.length === 0"
            :empty-text="keyword ? '找不到符合的結論' : '老師還沒有整理結論'"
            @retry="analyticsQuery.refetch()"
          >
            <ListCard
              v-for="k in results"
              :key="k.conclusion_id"
              v-model:expanded="expanded[k.conclusion_id]"
              :title="k.conclusion_id === myConclusionId ? `${k.title}（你的結論）` : k.title"
              :description="`人數：${k.count}（${k.percentage}%）`"
              :highlight="k.conclusion_id === myConclusionId"
              :expandable="k.students.length > 0"
            >
              <template #details>
                <ul class="text-body">
                  <li v-for="s in k.students" :key="s.student_id">{{ s.display_name }}</li>
                </ul>
              </template>
            </ListCard>
          </QueryState>
        </ListSection>
      </div>
    </QueryState>
  </div>
</template>
