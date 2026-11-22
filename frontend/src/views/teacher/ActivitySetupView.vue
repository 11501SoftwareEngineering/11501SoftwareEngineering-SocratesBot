<script setup lang="ts">
import AppBanner from '@/components/common/AppBanner.vue'
/**
 * 活動設定。同一個頁面有三種樣子：
 *   確認活動設定（剛新增，網址 ?new=1）  Figma「P11-2_Teacher_NewActivity」（node 750:2208）：
 *       多了「給 AI 的回饋」＋「重新產生」，按鈕是「儲存草稿」「發布活動」
 *   活動設定（草稿）                      Figma「P12-1_Teacher_Activity」（node 750:2375）：按鈕是「儲存」「發布活動」
 *   活動設定（已發布）                    Figma「P12-2_Teacher_Activity」（node 1015:4934）：唯讀，右上「檢視觀點」
 * 發布前確認「確定要發布嗎？」；有沒存的修改要離開時問「還沒儲存，確定要離開？」（Figma「P11_Confirm」）。
 *
 * 所見即所存：重新產生（開場訊息、依回饋）都帶畫面上的 setup，結果只填回畫面、不存檔；
 * 按「儲存」「發布」才把畫面上的內容存進去。
 * API：GET/PUT /topics/{topicId}/setup、POST .../setup/opening-message、POST .../setup/refine、POST /topics/{topicId}/publish
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { AGE_BANDS, courseKeys, MAX_TURNS } from '@/api/courses'
import { SETUP_FIELDS, topicKeys, topicsApi, type TopicSetup } from '@/api/topics'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import AppSelect from '@/components/form/AppSelect.vue'
import LongTextField from '@/components/form/LongTextField.vue'
import { SpinnerIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { useCourseTopics } from '@/composables/useCourse'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass, pageClass } from '@/lib/ui'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))
const topicId = computed(() => String(route.params.topicId ?? ''))
const isNew = computed(() => route.query.new === '1')

const { data: course } = useCourseTopics(courseId)
const isTeacher = computed(() => course.value?.my_role === 'teacher')

const { data, isPending, error, refetch } = useQuery({
  queryKey: computed(() => topicKeys.setup(topicId.value)),
  queryFn: () => topicsApi.getSetup(topicId.value),
  retry: false,
})

const editable = computed(() => data.value?.topic_status === 'setup')
const form = ref<TopicSetup | null>(null)
const saved = ref('')
watch(
  data,
  (value) => {
    if (!value) return
    form.value = { ...value.setup }
    saved.value = JSON.stringify(value.setup)
  },
  { immediate: true },
)
const dirty = computed(
  () => editable.value && !!form.value && JSON.stringify(form.value) !== saved.value,
)
const guard = useUnsavedGuard(dirty)

const notice = ref('')
const actionError = ref('')
function fail(fallback: string) {
  return (err: unknown) => {
    notice.value = ''
    actionError.value = getApiErrorMessage(err, fallback)
  }
}

// 儲存
const save = useMutation({
  mutationFn: () => topicsApi.saveSetup(topicId.value, form.value!),
  onSuccess: (result) => {
    queryClient.setQueryData(topicKeys.setup(topicId.value), result)
    void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
    actionError.value = ''
    notice.value = t('setup.saved')
    // 照 Prototype：新增活動第一次儲存後，網址換成既有活動設定（P12）
    if (route.query.new) void router.replace({ name: 'TeacherActivitySetup', params: route.params })
  },
  onError: fail(t('errors.saveFailed')),
})

// 重新產生開場訊息（不存檔）
const opening = useMutation({
  mutationFn: () => topicsApi.openingMessage(topicId.value, form.value!),
  onSuccess: (message) => {
    if (form.value) form.value.opening_message = message
    actionError.value = ''
    notice.value = t('setup.openingRegenerated')
  },
  onError: fail(t('errors.regenerateFailed')),
})

// 依回饋重新產生（不存檔）
const feedback = ref('')
const feedbackError = ref('')
const refine = useMutation({
  mutationFn: () => topicsApi.refine(topicId.value, form.value!, feedback.value.trim()),
  onSuccess: (result) => {
    form.value = { ...result.setup }
    feedback.value = ''
    actionError.value = ''
    notice.value = t('setup.refined')
  },
  onError: fail(t('errors.regenerateFailed')),
})
function handleRefine() {
  feedbackError.value = feedback.value.trim() ? '' : t('setup.feedbackRequired')
  if (!feedbackError.value) refine.mutate()
}

// 發布
const publishOpen = ref(false)
const publish = useMutation({
  mutationFn: () => topicsApi.publish(topicId.value, form.value!),
  onSuccess: (result) => {
    publishOpen.value = false
    queryClient.setQueryData(topicKeys.setup(topicId.value), result)
    void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
    guard.allow()
    // 照 Prototype：發布成功後直接到全班觀點（P13）
    void router.replace({ name: 'TeacherPerspective', params: route.params })
  },
  onError: (err) => {
    publishOpen.value = false
    fail(t('setup.publishFailed'))(err)
  },
})

const busy = computed(
  () =>
    save.isPending.value ||
    opening.isPending.value ||
    refine.isPending.value ||
    publish.isPending.value,
)
const turnOptions = computed(() =>
  MAX_TURNS.map((n) => ({ value: n, label: t('common.turns', { n }) })),
)
const textFields = SETUP_FIELDS.filter((f) => f.key !== 'opening_message')
const title = computed(() =>
  isNew.value && editable.value ? t('setup.confirmTitle') : t('setup.title'),
)
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      :title="title"
      :breadcrumbs="[
        { label: t('common.myCourses'), to: { name: 'TeacherCourses' } },
        {
          label: course?.name ?? t('common.course'),
          to: { name: 'TeacherCourse', params: { courseId } },
        },
      ]"
    >
      <template v-if="data && !isNew" #after-title>
        <StatusTag :tone="editable ? 'secondary' : 'primary'">{{
          editable ? t('activity.status.draft') : t('activity.status.published')
        }}</StatusTag>
        <Button v-if="!editable" as-child class="ml-auto">
          <RouterLink :to="{ name: 'TeacherPerspective', params: { courseId, topicId } }">{{
            t('activity.viewPerspective')
          }}</RouterLink>
        </Button>
      </template>
    </PageTitle>

    <QueryState
      class="mt-4"
      :loading="isPending"
      :error="error"
      :error-text="t('setup.loadError')"
      @retry="refetch()"
    >
      <form
        v-if="form"
        :class="[
          editable ? cardClass : cardClass.replace('bg-card', 'bg-border'),
          'flex flex-col gap-4 p-5 sm:px-8',
        ]"
        @submit.prevent="save.mutate()"
      >
        <AppBanner v-if="!editable" type="lock">{{ t('setup.locked') }}</AppBanner>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <AppSelect
            v-model="form.age_band"
            :label="t('common.ageBand')"
            :options="AGE_BANDS"
            :disabled="!editable || busy"
          />
          <AppSelect
            v-model="form.max_turns"
            :label="t('common.turnsLabel')"
            :options="turnOptions"
            :disabled="!editable || busy"
          />
        </div>
        <LongTextField
          v-for="field in textFields"
          :key="field.key"
          v-model="form[field.key] as string"
          :label="field.label"
          :readonly="!editable"
          :disabled="busy"
        />
        <LongTextField
          v-model="form.opening_message"
          :label="t('setupFields.opening_message')"
          :readonly="!editable"
          :disabled="busy"
          :action-label="editable ? t('setup.regenerate') : undefined"
          :action-aria-label="t('setup.regenerateOpeningAria')"
          :action-pending="opening.isPending.value"
          @action="opening.mutate()"
        />

        <div v-if="editable && isNew" class="flex flex-col gap-2 sm:flex-row sm:items-end">
          <LongTextField
            v-model="feedback"
            class="flex-1"
            :label="t('setup.feedback')"
            :placeholder="t('setup.feedbackPlaceholder')"
            :error="feedbackError"
            :disabled="busy"
          />
          <Button
            type="button"
            variant="secondary"
            class="sm:mb-[2px]"
            :disabled="busy"
            :aria-label="t('setup.regenerateFeedbackAria')"
            @click="handleRefine"
          >
            <SpinnerIcon v-if="refine.isPending.value" class="animate-spin" />
            {{ refine.isPending.value ? t('setup.regenerating') : t('setup.regenerate') }}
          </Button>
        </div>

        <p
          v-if="refine.isPending.value"
          role="status"
          class="flex items-center gap-2 text-body text-muted-foreground"
        >
          <SpinnerIcon class="animate-spin" /> {{ t('setup.refining') }}
        </p>
        <AppBanner v-if="actionError" type="error">{{ actionError }}</AppBanner>
        <AppBanner v-else-if="notice" type="success">{{ notice }}</AppBanner>

        <div v-if="editable" class="flex justify-end gap-3">
          <Button type="submit" variant="secondary" :disabled="busy">
            {{
              save.isPending.value
                ? t('common.saving')
                : isNew
                  ? t('setup.saveDraft')
                  : t('common.save')
            }}
          </Button>
          <Button v-if="isTeacher" type="button" :disabled="busy" @click="publishOpen = true">{{
            t('setup.publish')
          }}</Button>
        </div>
      </form>
    </QueryState>

    <ConfirmDialog
      v-model:open="publishOpen"
      :title="t('setup.publishTitle')"
      :description="t('setup.publishDescription')"
      :confirm-text="t('setup.publishConfirm')"
      :loading="publish.isPending.value"
      @confirm="publish.mutate()"
    />
    <ConfirmDialog
      v-model:open="guard.open.value"
      :title="t('setup.leaveTitle')"
      :description="t('setup.leaveDescription')"
      :confirm-text="t('setup.leave')"
      :cancel-text="t('setup.stay')"
      destructive
      confirm-first
      @confirm="guard.leave()"
    />
  </div>
</template>
