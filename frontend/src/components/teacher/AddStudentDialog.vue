<script setup lang="ts">
/**
 * 用學生帳號把學生加進課程。Figma 沒有這個畫面，但被移出課程的學生不能再用代碼加入，
 * 只能由老師加回來，所以需要這個入口。
 * API：POST /teacher/courses/{courseId}/students
 */
import { ref, watch } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { teacherApi, teacherKeys } from '@/api/teacher'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'

const props = defineProps<{ courseId: string }>()
const open = defineModel<boolean>('open', { default: false })

const queryClient = useQueryClient()
const account = ref('')
const error = ref('')

watch(open, (isOpen) => {
  if (!isOpen) return
  account.value = ''
  error.value = ''
})

const mutation = useMutation({
  mutationFn: () => teacherApi.addStudent(props.courseId, account.value.trim()),
  onSuccess: () => {
    open.value = false
    void queryClient.invalidateQueries({ queryKey: teacherKeys.students(props.courseId) })
    void queryClient.invalidateQueries({ queryKey: teacherKeys.courses })
  },
  onError: (err) => (error.value = getApiErrorMessage(err, '加入失敗，請稍後再試')),
})

function handleSubmit() {
  const value = account.value.trim()
  error.value = !value ? '請輸入學生帳號' : value.length > 64 ? '帳號最多 64 個字' : ''
  if (!error.value) mutation.mutate()
}
</script>

<template>
  <FormDialog
    v-model:open="open"
    title="加入學生"
    description="輸入學生註冊時用的帳號，就能把他加進這門課。"
    submit-text="加入"
    :loading="mutation.isPending.value"
    @submit="handleSubmit"
  >
    <FormField v-slot="field" label="學生帳號" :error="error">
      <Input
        v-model="account"
        v-bind="field"
        :id="field.id"
        autocomplete="off"
        spellcheck="false"
      />
    </FormField>
  </FormDialog>
</template>
