<script setup lang="ts">
/**
 * 輸入課程代碼加入課程。對應 Figma「JoinCourse」（node 266:2304）。
 * API：POST /courses/join
 */
import { ref, watch } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { courseKeys, coursesApi } from '@/api/courses'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import { Input } from '@/components/ui/input'
import { getApiErrorMessage } from '@/lib/utils'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

/** 後端的課程代碼：8 個字元 */
const INVITE_CODE_LENGTH = 8

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
  mutationFn: () => coursesApi.join(code.value.trim().toUpperCase()),
  onSuccess: (course) => {
    open.value = false
    void queryClient.invalidateQueries({ queryKey: courseKeys.all })
    emit('joined', course.name)
  },
  onError: (err) => (error.value = getApiErrorMessage(err, t('courses.joinFailed'))),
})

function handleSubmit() {
  const value = code.value.trim()
  error.value = !value
    ? t('courses.inviteRequired')
    : value.length !== INVITE_CODE_LENGTH
      ? t('courses.inviteLength', { n: INVITE_CODE_LENGTH })
      : ''
  if (!error.value) mutation.mutate()
}
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="t('courses.join')"
    :submit-text="t('courses.joinSubmit')"
    :loading="mutation.isPending.value"
    @submit="handleSubmit"
  >
    <FormField v-slot="field" :label="t('courses.inviteCode')" :error="error">
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
