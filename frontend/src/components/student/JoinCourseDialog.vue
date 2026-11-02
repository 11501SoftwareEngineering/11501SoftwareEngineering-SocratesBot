<script setup lang="ts">
/**
 * 輸入課程代碼加入課程。對應 Figma「JoinCourse」（node 266:2304）。
 * API：POST /student/courses/join
 */
import { ref, watch } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { INVITE_CODE_LENGTH, studentApi, studentKeys } from '@/api/student'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ joined: [courseName: string] }>()

const queryClient = useQueryClient()
const code = ref('')
const error = ref('')

watch(open, (isOpen) => {
  if (!isOpen) return
  code.value = ''
  error.value = ''
})

const mutation = useMutation({
  mutationFn: () => studentApi.joinCourse(code.value.trim().toUpperCase()),
  onSuccess: (course) => {
    open.value = false
    void queryClient.invalidateQueries({ queryKey: studentKeys.courses })
    emit('joined', course.name)
  },
  onError: (err) => (error.value = getApiErrorMessage(err, '加入失敗，請稍後再試')),
})

function handleSubmit() {
  const value = code.value.trim()
  error.value = !value
    ? '請輸入課程代碼'
    : value.length !== INVITE_CODE_LENGTH
      ? `課程代碼是 ${INVITE_CODE_LENGTH} 個字元，請再確認一次`
      : ''
  if (!error.value) mutation.mutate()
}
</script>

<template>
  <FormDialog
    v-model:open="open"
    title="加入課程"
    submit-text="加入"
    :loading="mutation.isPending.value"
    @submit="handleSubmit"
  >
    <FormField v-slot="field" label="課程代碼" :error="error">
      <Input
        v-model="code"
        v-bind="field"
        :id="field.id"
        autocomplete="off"
        autocapitalize="characters"
        :maxlength="INVITE_CODE_LENGTH + 4"
        spellcheck="false"
        class="font-mono uppercase"
      />
    </FormField>
  </FormDialog>
</template>
