<script setup lang="ts">
/**
 * 新增活動。對應 Figma「P11-1_Teacher_NewActivity」（node 750:2131）、
 * 「P11-1_Teacher_NewActivity_Loading」（node 1022:2995）。
 *   年齡層、回合數、課程描述（最多 6000 字）→「產生設定」
 *   AI 整理時顯示「AI 正在整理活動設定，請稍候…」，按鈕變成「處理中…」
 * 成功後到「確認活動設定」（同一個設定頁，網址帶 ?new=1）。
 *
 * API：POST /courses/{courseId}/topics（docs/API功能規格.md v0.2「建立題目」）
 *   規格還要 content_language、model_id，但 Figma 沒有這兩個欄位：
 *   送目前的介面語言，模型送老師的預設模型（拿得到才送）。
 */
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { aiApi, aiKeys } from '@/api/ai'
import { AGE_BANDS, courseKeys, MAX_TURNS, type AgeBand, type MaxTurns } from '@/api/courses'
import { LONG_TEXT_MAX, topicKeys, topicsApi } from '@/api/topics'
import PageTitle from '@/components/common/PageTitle.vue'
import AppSelect from '@/components/form/AppSelect.vue'
import LongTextField from '@/components/form/LongTextField.vue'
import { SpinnerIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { useCourse } from '@/composables/useCourse'
import { useUiLanguage } from '@/composables/useUiLanguage'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass, pageClass } from '@/lib/ui'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const { data: course } = useCourse(courseId)
const { language } = useUiLanguage()

// 老師的預設模型；助教沒有自己的設定，就用課程的預設模型
const settings = useQuery({ queryKey: aiKeys.settings, queryFn: aiApi.settings, retry: false })
const modelId = computed(
  () => settings.data.value?.default_model?.id ?? course.value?.default_model?.id,
)

const form = reactive<{ age_band: AgeBand; max_turns: MaxTurns; course_description: string }>({
  age_band: '16-18',
  max_turns: 10,
  course_description: '',
})
const descriptionError = ref('')
const formError = ref('')

const create = useMutation({
  mutationFn: () =>
    topicsApi.create(courseId.value, {
      age_band: form.age_band,
      max_turns: form.max_turns,
      course_description: form.course_description.trim(),
      content_language: language.value,
      ...(modelId.value ? { model_id: modelId.value } : {}),
    }),
  onSuccess: (result) => {
    queryClient.setQueryData(topicKeys.setup(result.topic_id), result)
    void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
    void router.replace({
      name: 'TeacherActivitySetup',
      params: { courseId: courseId.value, topicId: result.topic_id },
      query: { new: '1' },
    })
  },
  onError: (err) => (formError.value = getApiErrorMessage(err, 'AI 整理失敗，請稍後再試')),
})

function handleSubmit() {
  descriptionError.value = form.course_description.trim() ? '' : '請輸入課程描述'
  formError.value = ''
  if (!descriptionError.value) create.mutate()
}

const turnOptions = MAX_TURNS.map((n) => ({ value: n, label: `${n} 回合` }))
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      title="新增活動"
      :breadcrumbs="[
        { label: '我的課程', to: { name: 'TeacherCourses' } },
        { label: course?.name ?? '課程', to: { name: 'TeacherCourse', params: { courseId } } },
      ]"
    />
    <form
      :class="[cardClass, 'mt-4 flex flex-col gap-4 p-5 sm:px-8']"
      @submit.prevent="handleSubmit"
    >
      <div class="grid gap-4 sm:grid-cols-2">
        <AppSelect
          v-model="form.age_band"
          label="年齡層"
          :options="AGE_BANDS"
          :disabled="create.isPending.value"
        />
        <AppSelect
          v-model="form.max_turns"
          label="回合數"
          :options="turnOptions"
          :disabled="create.isPending.value"
        />
      </div>
      <LongTextField
        v-model="form.course_description"
        label="課程描述"
        :maxlength="LONG_TEXT_MAX"
        :error="descriptionError"
        :disabled="create.isPending.value"
        placeholder="這次想讓學生探究什麼？例如課程單元、學生程度、想討論的爭議"
      />
      <p
        v-if="create.isPending.value"
        role="status"
        class="flex items-center gap-2 text-body text-muted-foreground"
      >
        <SpinnerIcon class="animate-spin" /> AI 正在整理活動設定，請稍候…
      </p>
      <p v-if="formError" role="alert" class="text-body text-destructive">{{ formError }}</p>
      <div class="flex justify-end">
        <Button type="submit" :disabled="create.isPending.value">
          {{ create.isPending.value ? '處理中…' : '產生設定' }}
        </Button>
      </div>
    </form>
  </div>
</template>
