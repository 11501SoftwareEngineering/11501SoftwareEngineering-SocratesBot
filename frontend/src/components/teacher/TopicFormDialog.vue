<script setup lang="ts">
/**
 * 新增／編輯問題。對應 Figma「AddQuistion」（node 266:2276）。
 * 年齡層、回合數是 Figma 上的選項，後端還沒有欄位，只在 features.topicSettings 打開時顯示。
 */
import { reactive, ref, watch } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  AGE_RANGES,
  ROUND_OPTIONS,
  teacherApi,
  teacherKeys,
  type TeacherTopic,
} from '@/api/teacher'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import OptionGroup from '@/components/common/OptionGroup.vue'
import { Textarea } from '@/components/ui/textarea'
import { features } from '@/config/features'
import { getApiErrorMessage } from '@/lib/utils'

const props = defineProps<{ courseId: string; topic?: TeacherTopic | null }>()
const open = defineModel<boolean>('open', { default: false })

const queryClient = useQueryClient()
const form = reactive({ title: '', ageRange: '13-15', maxRounds: 10 })
const titleError = ref('')
const formError = ref('')

const ageOptions = AGE_RANGES.map((value) => ({ value: value as string, label: value }))
const roundOptions = ROUND_OPTIONS.map((o) => ({
  value: o.value as number,
  label: `${o.label}(${o.value})`,
}))

watch(open, (isOpen) => {
  if (!isOpen) return
  form.title = props.topic?.title ?? ''
  form.ageRange = props.topic?.age_range ?? '13-15'
  form.maxRounds = props.topic?.max_rounds ?? 10
  titleError.value = ''
  formError.value = ''
})

const mutation = useMutation({
  mutationFn: async () => {
    const payload = {
      title: form.title.trim(),
      // 對話框沒有「描述」欄位（Figma 沒有），編輯時保留原本的描述
      description: props.topic?.description ?? null,
      // 年齡層、回合數後端還沒有欄位，只有假後端會送
      ...(features.topicSettings ? { age_range: form.ageRange, max_rounds: form.maxRounds } : {}),
    }
    if (props.topic) await teacherApi.updateTopic(props.topic.topic_id, payload)
    else await teacherApi.createTopic({ course_id: props.courseId, ...payload })
  },
  onSuccess: () => {
    open.value = false
    void queryClient.invalidateQueries({ queryKey: teacherKeys.course(props.courseId) })
    void queryClient.invalidateQueries({ queryKey: teacherKeys.courses })
  },
  onError: (error) => (formError.value = getApiErrorMessage(error, '儲存失敗，請稍後再試')),
})

function handleSubmit() {
  const title = form.title.trim()
  titleError.value = !title ? '請輸入問題' : title.length > 255 ? '問題最多 255 個字' : ''
  formError.value = ''
  if (!titleError.value) mutation.mutate()
}
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="topic ? '編輯問題' : '新增問題'"
    :submit-text="topic ? '儲存' : '新增'"
    :loading="mutation.isPending.value"
    :error="formError"
    @submit="handleSubmit"
  >
    <FormField v-slot="field" label="輸入問題" align-top :error="titleError">
      <Textarea
        v-model="form.title"
        v-bind="field"
        :id="field.id"
        :rows="4"
        placeholder="例如：善意的謊言是對的嗎？"
      />
    </FormField>
    <template v-if="features.topicSettings">
      <OptionGroup v-model="form.ageRange" label="年齡層" :options="ageOptions" />
      <OptionGroup v-model="form.maxRounds" label="回合數" :options="roundOptions" />
    </template>
  </FormDialog>
</template>
