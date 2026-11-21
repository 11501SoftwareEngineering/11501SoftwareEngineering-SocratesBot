<script setup lang="ts">
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
import { RefreshIcon, SpinnerIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { useCourseTopics } from '@/composables/useCourse'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass, pageClass } from '@/lib/ui'

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
    notice.value = '已儲存'
    // 照 Prototype：新增活動第一次儲存後，網址換成既有活動設定（P12）
    if (route.query.new) void router.replace({ name: 'TeacherActivitySetup', params: route.params })
  },
  onError: fail('儲存失敗，請稍後再試'),
})

// 重新產生開場訊息（不存檔）
const opening = useMutation({
  mutationFn: () => topicsApi.openingMessage(topicId.value, form.value!),
  onSuccess: (message) => {
    if (form.value) form.value.opening_message = message
    actionError.value = ''
    notice.value = '已重新產生開場訊息，記得儲存'
  },
  onError: fail('重新產生失敗，請稍後再試'),
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
    notice.value = '已依回饋重新產生，確認沒問題再儲存或發布'
  },
  onError: fail('重新產生失敗，請稍後再試'),
})
function handleRefine() {
  feedbackError.value = feedback.value.trim() ? '' : '請先寫下想請 AI 怎麼修改'
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
    fail('發布失敗，請確認每個欄位都填好了')(err)
  },
})

const busy = computed(
  () =>
    save.isPending.value ||
    opening.isPending.value ||
    refine.isPending.value ||
    publish.isPending.value,
)
const turnOptions = MAX_TURNS.map((n) => ({ value: n, label: `${n} 回合` }))
const textFields = SETUP_FIELDS.filter((f) => f.key !== 'opening_message')
const title = computed(() => (isNew.value && editable.value ? '確認活動設定' : '活動設定'))
</script>

<template>
  <div :class="pageClass">
    <PageTitle
      :title="title"
      :breadcrumbs="[
        { label: '我的課程', to: { name: 'TeacherCourses' } },
        { label: course?.name ?? '課程', to: { name: 'TeacherCourse', params: { courseId } } },
      ]"
    >
      <template v-if="data && !isNew" #after-title>
        <StatusTag :tone="editable ? 'secondary' : 'primary'">{{
          editable ? '草稿' : '已發布'
        }}</StatusTag>
        <Button v-if="!editable" as-child class="ml-auto">
          <RouterLink :to="{ name: 'TeacherPerspective', params: { courseId, topicId } }"
            >檢視觀點</RouterLink
          >
        </Button>
      </template>
    </PageTitle>

    <QueryState
      class="mt-4"
      :loading="isPending"
      :error="error"
      error-text="無法取得活動設定"
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
        <p v-if="!editable" class="text-body text-destructive">
          已發布的設定已鎖定，以下內容無法修改
        </p>
        <div class="grid gap-4 sm:grid-cols-2">
          <AppSelect
            v-model="form.age_band"
            label="年齡層"
            :options="AGE_BANDS"
            :disabled="!editable || busy"
          />
          <AppSelect
            v-model="form.max_turns"
            label="回合數"
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
          label="開場訊息"
          :readonly="!editable"
          :disabled="busy"
        >
          <template v-if="editable" #action>
            <button
              type="button"
              class="flex items-center gap-1 rounded text-body text-primary-dark outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
              :disabled="busy"
              aria-label="重新產生開場訊息"
              @click="opening.mutate()"
            >
              <SpinnerIcon v-if="opening.isPending.value" class="size-4 animate-spin" />
              <RefreshIcon v-else class="size-4" />
              重新產生
            </button>
          </template>
        </LongTextField>

        <div v-if="editable && isNew" class="flex flex-col gap-2 sm:flex-row sm:items-end">
          <LongTextField
            v-model="feedback"
            class="flex-1"
            label="給 AI 的回饋"
            placeholder="例如：背景資訊太長了，精簡一點；核心問題改得更貼近國中生"
            :error="feedbackError"
            :disabled="busy"
          />
          <Button
            type="button"
            variant="secondary"
            class="sm:mb-[2px]"
            :disabled="busy"
            aria-label="依回饋重新產生"
            @click="handleRefine"
          >
            <SpinnerIcon v-if="refine.isPending.value" class="animate-spin" />
            {{ refine.isPending.value ? '產生中…' : '重新產生' }}
          </Button>
        </div>

        <p
          v-if="refine.isPending.value"
          role="status"
          class="flex items-center gap-2 text-body text-muted-foreground"
        >
          <SpinnerIcon class="animate-spin" /> AI 正在依回饋修改，請稍候…
        </p>
        <p v-if="actionError" role="alert" class="text-body text-destructive">{{ actionError }}</p>
        <p v-else-if="notice" role="status" class="text-body text-muted-foreground">{{ notice }}</p>

        <div v-if="editable" class="flex justify-end gap-3">
          <Button type="submit" variant="secondary" :disabled="busy">
            {{ save.isPending.value ? '儲存中…' : isNew ? '儲存草稿' : '儲存' }}
          </Button>
          <Button v-if="isTeacher" type="button" :disabled="busy" @click="publishOpen = true"
            >發布活動</Button
          >
        </div>
      </form>
    </QueryState>

    <ConfirmDialog
      v-model:open="publishOpen"
      title="確定要發布嗎？"
      description="發布之後就不能再修改設定了"
      confirm-text="發布"
      :loading="publish.isPending.value"
      @confirm="publish.mutate()"
    />
    <ConfirmDialog
      v-model:open="guard.open.value"
      title="還沒儲存，確定要離開？"
      description="修改的內容會不見"
      confirm-text="離開"
      cancel-text="留下"
      destructive
      confirm-first
      @confirm="guard.leave()"
    />
  </div>
</template>
