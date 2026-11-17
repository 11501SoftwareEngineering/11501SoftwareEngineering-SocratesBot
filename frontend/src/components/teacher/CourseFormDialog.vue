<script setup lang="ts">
/**
 * 新增／編輯課程。對應 Figma「P09_AddCourse」（node 266:1436）。
 * API：POST /courses、PUT /courses/{courseId}
 * 傳入 course 就是編輯模式。
 */
import { reactive, ref, watch } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { courseKeys, coursesApi, type CourseSummary } from '@/api/courses'
import FormDialog from '@/components/common/FormDialog.vue'
import FormField from '@/components/common/FormField.vue'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { getApiErrorMessage } from '@/lib/utils'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  course?: Pick<CourseSummary, 'course_id' | 'name' | 'description'> | null
}>()
const open = defineModel<boolean>('open', { default: false })

const queryClient = useQueryClient()
const form = reactive({ name: '', description: '' })
const nameError = ref('')
const formError = ref('')

watch(open, (isOpen) => {
  if (!isOpen) return
  form.name = props.course?.name ?? ''
  form.description = props.course?.description ?? ''
  nameError.value = ''
  formError.value = ''
})

const mutation = useMutation({
  mutationFn: async () => {
    const payload = { name: form.name.trim(), description: form.description.trim() }
    if (props.course) await coursesApi.update(props.course.course_id, payload)
    else await coursesApi.create(payload)
  },
  onSuccess: () => {
    open.value = false
    void queryClient.invalidateQueries({ queryKey: courseKeys.all })
  },
  onError: (error) => (formError.value = getApiErrorMessage(error, t('errors.saveFailed'))),
})

function handleSubmit() {
  const name = form.name.trim()
  nameError.value = !name
    ? t('courses.nameRequired')
    : name.length > 255
      ? t('courses.nameTooLong')
      : ''
  formError.value = ''
  if (!nameError.value) mutation.mutate()
}
</script>

<template>
  <FormDialog
    v-model:open="open"
    :title="course ? t('courses.editCourse') : t('courses.addCourse')"
    :submit-text="course ? t('common.save') : t('common.add')"
    :loading="mutation.isPending.value"
    :error="formError"
    @submit="handleSubmit"
  >
    <FormField v-slot="field" :label="t('courses.courseName')" :error="nameError">
      <Input v-model="form.name" v-bind="field" :id="field.id" autocomplete="off" />
    </FormField>
    <FormField v-slot="field" :label="t('courses.courseDescription')" align-top>
      <Textarea v-model="form.description" v-bind="field" :id="field.id" :rows="6" />
    </FormField>
  </FormDialog>
</template>
