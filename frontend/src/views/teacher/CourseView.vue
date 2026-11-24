<script setup lang="ts">
/**
 * 老師／助教：課程頁。對應 Figma「P10-1_Teacher_Course」（課程成員，node 171:188）、
 * 「P10-2_Teacher_Course」（助教管理，node 692:3594）、「P10_AddTA_Confirm」。
 *   上方：麵包屑、課程名稱、課程代碼（可複製）、課程描述
 *   左邊：探究活動（草稿 →「繼續編輯↗」到活動設定；已發布 →「檢視觀點↗」到全班觀點）
 *   右邊：課程成員｜助教管理（助教管理只有老師看得到）
 * API：GET /courses/{courseId}、GET /courses/{courseId}/topics、DELETE /topics/{topicId}、
 *      GET /courses/{courseId}/members?role=student|ta、DELETE /courses/{courseId}/students/{userId}、
 *      POST /courses/{courseId}/tas（四個權限全開，Figma 沒有權限設定畫面）、DELETE /courses/{courseId}/tas/{userId}
 * 助教依權限：有 edit_topics 才能新增活動；有 view_members 才看得到課程成員；不能刪除或管理助教。
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  courseKeys,
  coursesApi,
  TA_PERMISSIONS,
  type CourseMember,
  type TaPermission,
  type TopicListItem,
} from '@/api/courses'
import { summariesApi, summaryKeys } from '@/api/summaries'
import { topicsApi } from '@/api/topics'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import SectionHeading from '@/components/common/SectionHeading.vue'
import TabNav from '@/components/common/TabNav.vue'
import ActivityCard from '@/components/course/ActivityCard.vue'
import MemberCard from '@/components/course/MemberCard.vue'
import { AddRingIcon, TrashIcon, UserDeleteIcon } from '@/components/icons'
import CopyButton from '@/components/common/CopyButton.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useCourse, useCourseTopics } from '@/composables/useCourse'
import { useSearch } from '@/composables/useSearch'
import { getApiErrorMessage } from '@/lib/utils'
import { UserPlus } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const route = useRoute()
const queryClient = useQueryClient()
const courseId = computed(() => String(route.params.courseId ?? ''))

const { data: course } = useCourse(courseId)
const topicsQuery = useCourseTopics(courseId)
const role = computed(() => topicsQuery.data.value?.my_role ?? course.value?.my_role)
const permissions = computed(() => topicsQuery.data.value?.my_permissions ?? [])
const isTeacher = computed(() => role.value === 'teacher')
const can = (p: TaPermission) => isTeacher.value || permissions.value.includes(p)

// ---------- 課程代碼 ----------
const inviteCode = computed(
  () => course.value?.invite_code ?? topicsQuery.data.value?.invite_code ?? '',
)

// ---------- 探究活動 ----------
const { keyword, results: topics } = useSearch(
  () => topicsQuery.data.value?.topics ?? [],
  (t) => [t.title, t.description ?? ''],
)

// 摘要發布後 topic 還是 summary 階段，課程列表也沒有「是否已發布」的欄位，
// 所以 summary 階段的活動各查一次已發布的摘要（課程成員都能查；還沒發布時 summary 是 null）。
// 發布或撤回時全班觀點頁會讓 ['topics', id, 'summary'] 底下的快取失效，回到這頁就會更新。
// TODO: 後端在 GET /courses/{id}/topics 加上發布狀態後，改用那個欄位，拿掉這些請求
const summaryTopicIds = computed(() =>
  (topicsQuery.data.value?.topics ?? [])
    .filter((topic) => topic.topic_status === 'summary')
    .map((topic) => topic.topic_id),
)
const publishedQueries = useQueries({
  queries: computed(() =>
    summaryTopicIds.value.map((topicId) => ({
      queryKey: summaryKeys.published(topicId),
      queryFn: () => summariesApi.published(topicId),
    })),
  ),
})
const publishedTopicIds = computed(
  () => new Set(summaryTopicIds.value.filter((_, i) => !!publishedQueries.value[i]?.data)),
)

function cardFor(topic: TopicListItem) {
  const params = { courseId: courseId.value, topicId: topic.topic_id }
  if (topic.topic_status === 'setup') {
    return {
      status: { label: t('activity.status.draft'), tone: 'secondary' as const },
      link: can('edit_topics')
        ? { label: t('activity.continueEditing'), to: { name: 'TeacherActivitySetup', params } }
        : undefined,
      note: can('edit_topics') ? undefined : t('activity.awaitingTeacher'),
    }
  }
  return {
    status:
      topic.topic_status !== 'summary'
        ? { label: t('activity.status.published'), tone: 'primary' as const }
        : publishedTopicIds.value.has(topic.topic_id)
          ? { label: t('activity.status.summaryPublished'), tone: 'primary' as const }
          : { label: t('activity.status.summarizing'), tone: 'primary' as const },
    link:
      can('view_reports') || can('edit_summary')
        ? { label: t('activity.viewPerspective'), to: { name: 'TeacherPerspective', params } }
        : undefined,
    progress: { done: topic.answered_count ?? 0, total: topic.student_count ?? 0 },
  }
}

const removeTopic = useConfirmAction((topic: TopicListItem) => topicsApi.remove(topic.topic_id), {
  onSuccess: () => queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) }),
  errorText: t('errors.deleteFailed'),
})

// ---------- 課程成員／助教管理 ----------
type PanelTab = 'students' | 'tas'
const panel = ref<PanelTab>('students')

const students = useQuery({
  queryKey: computed(() => courseKeys.members(courseId.value, 'student')),
  queryFn: () => coursesApi.members(courseId.value, 'student'),
  enabled: () => !!role.value && can('view_members'),
})
const tas = useQuery({
  queryKey: computed(() => courseKeys.members(courseId.value, 'ta')),
  queryFn: () => coursesApi.members(courseId.value, 'ta'),
  enabled: () => isTeacher.value,
})

const panelTabs = computed(() => [
  ...(can('view_members')
    ? [
        {
          key: 'students' as const,
          label: t('course.members'),
          count: students.data.value?.length ?? 0,
        },
      ]
    : []),
  ...(isTeacher.value ? [{ key: 'tas' as const, label: t('course.tas') }] : []),
])

function refreshMembers() {
  void queryClient.invalidateQueries({ queryKey: ['courses', courseId.value, 'members'] })
  void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
}

const removeStudent = useConfirmAction(
  (m: CourseMember) => coursesApi.removeStudent(courseId.value, m.user_id),
  { onSuccess: refreshMembers, errorText: t('errors.removeFailed') },
)
const removeTa = useConfirmAction(
  (m: CourseMember) => coursesApi.removeTa(courseId.value, m.user_id),
  {
    onSuccess: refreshMembers,
    errorText: t('errors.removeFailed'),
  },
)

// 新增助教：輸入帳號 →「＋助教」→ 先請後端檢查（check: true，順便拿到姓名）→ 確認視窗 → 送出
// （預設給全部四項權限，之後可以從卡片修改）
const taAccount = ref('')
/** 檢查通過時後端回傳的姓名，確認視窗顯示（Figma「P10_AddTA_Confirm」） */
const taName = ref('')
const taError = ref('')
const confirmTaOpen = ref(false)
// 照 Figma 沒有權限設定畫面：新增助教時四個權限全開
const DEFAULT_TA_PERMISSIONS = TA_PERMISSIONS.map((p) => p.value)
const checkTa = useMutation({
  mutationFn: (account: string) =>
    coursesApi.addTa(courseId.value, account, DEFAULT_TA_PERMISSIONS, { check: true }),
  onSuccess: (result) => {
    taName.value = result.name
    confirmTaOpen.value = true
  },
  onError: (err) => (taError.value = getApiErrorMessage(err, t('course.addTaFailed'))),
})
function askAddTa() {
  const account = taAccount.value.trim()
  taError.value = account ? '' : t('course.accountRequired')
  if (!taError.value) checkTa.mutate(account)
}
const addTa = useMutation({
  mutationFn: () =>
    coursesApi.addTa(courseId.value, taAccount.value.trim(), DEFAULT_TA_PERMISSIONS),
  onSuccess: () => {
    confirmTaOpen.value = false
    taAccount.value = ''
    refreshMembers()
  },
  onError: (err) => (taError.value = getApiErrorMessage(err, t('course.addTaFailed'))),
})

const breadcrumbs = computed(() => [
  {
    label: t('common.myCourses'),
    to: { name: 'TeacherCourses' },
  },
])
</script>

<template>
  <div class="mx-auto w-full max-w-[1237px] px-4 pt-[30px] pb-12">
    <PageTitle
      class="lg:px-5"
      :title="course?.name ?? topicsQuery.data.value?.name ?? t('common.course')"
      :breadcrumbs="breadcrumbs"
      :description="course?.description"
    >
      <template #after-title>
        <span class="flex items-center gap-2 text-header text-foreground">
          {{ t('courses.inviteCodeLabel', { code: inviteCode }) }}
          <CopyButton
            v-if="inviteCode"
            :text="inviteCode"
            :label="t('course.copyCode')"
            :done-label="t('course.codeCopied')"
          />
        </span>
      </template>
    </PageTitle>

    <div
      class="mt-4 grid items-start gap-8 lg:grid-cols-[minmax(0,774px)_minmax(0,431px)] lg:gap-0"
    >
      <!-- 探究活動 -->
      <section class="flex min-w-0 flex-col gap-2 lg:px-5 lg:py-2">
        <SectionHeading
          :title="t('activity.title')"
          :count="topicsQuery.data.value?.topics.length ?? 0"
        >
          <template v-if="can('edit_topics')" #actions>
            <Button as-child>
              <RouterLink :to="{ name: 'TeacherNewActivity', params: { courseId } }">
                <AddRingIcon /> {{ t('activity.add') }}
              </RouterLink>
            </Button>
          </template>
        </SectionHeading>
        <SearchInput v-model="keyword" :label="t('activity.search')" />
        <QueryState
          :loading="topicsQuery.isPending.value"
          :error="topicsQuery.error.value"
          :empty="topics.length === 0"
          :empty-text="t('activity.notFound')"
          :error-text="t('activity.loadError')"
          @retry="topicsQuery.refetch()"
        >
          <template v-if="can('edit_topics')" #empty-action>
            {{ t('common.tryPrefix')
            }}<RouterLink
              :to="{ name: 'TeacherNewActivity', params: { courseId } }"
              class="rounded underline underline-offset-4 outline-none hover:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >{{ t('activity.add') }}</RouterLink
            >
          </template>
          <div class="flex flex-col gap-2">
            <ActivityCard
              v-for="topic in topics"
              :key="topic.topic_id"
              :title="topic.title"
              :description="topic.description"
              :age-band="topic.age_band"
              :max-turns="topic.max_turns"
              v-bind="cardFor(topic)"
            >
              <template v-if="isTeacher" #actions>
                <Button
                  variant="ghost-danger"
                  size="icon-sm"
                  :aria-label="t('activity.deleteAria', { title: topic.title })"
                  @click="removeTopic.ask(topic)"
                >
                  <TrashIcon />
                </Button>
              </template>
            </ActivityCard>
          </div>
        </QueryState>
      </section>

      <!-- 課程成員｜助教管理 -->
      <section
        v-if="panelTabs.length"
        class="flex min-w-0 flex-col gap-[22px] px-4 py-2"
        :aria-label="t('course.membersAndTas')"
      >
        <TabNav v-model="panel" :items="panelTabs" :label="t('course.membersAndTas')" size="lg" />

        <QueryState
          v-if="panel === 'students' && can('view_members')"
          :loading="students.isPending.value"
          :error="students.error.value"
          :empty="(students.data.value?.length ?? 0) === 0"
          :empty-text="t('course.noStudents')"
          :error-text="t('course.membersError')"
          @retry="students.refetch()"
        >
          <div class="flex flex-col gap-2">
            <MemberCard
              v-for="m in students.data.value"
              :key="m.user_id"
              :name="m.name"
              :account="m.account_id"
            >
              <template v-if="isTeacher" #actions>
                <Button
                  variant="ghost-danger"
                  size="icon-sm"
                  :aria-label="t('course.removeStudentAria', { name: m.name })"
                  @click="removeStudent.ask(m)"
                >
                  <UserDeleteIcon />
                </Button>
              </template>
            </MemberCard>
          </div>
        </QueryState>

        <template v-if="panel === 'tas' && isTeacher">
          <form class="flex flex-col gap-1" @submit.prevent="askAddTa">
            <div class="flex items-center gap-3">
              <label for="ta-account" class="sr-only">{{ t('course.taAccount') }}</label>
              <Input
                id="ta-account"
                v-model="taAccount"
                :placeholder="t('course.accountPlaceholder')"
                autocomplete="off"
                class="h-9 flex-1 rounded-2xl bg-card"
                :aria-invalid="!!taError"
              />
              <Button type="submit" :disabled="checkTa.isPending.value"
                ><UserPlus class="size-6" aria-hidden="true" /> {{ t('course.addTa') }}</Button
              >
            </div>
            <p v-if="taError" role="alert" class="text-body text-destructive">{{ taError }}</p>
          </form>
          <QueryState
            :loading="tas.isPending.value"
            :error="tas.error.value"
            :empty="(tas.data.value?.length ?? 0) === 0"
            :empty-text="t('course.noTas')"
            :error-text="t('course.tasError')"
            @retry="tas.refetch()"
          >
            <div class="flex flex-col gap-2">
              <MemberCard
                v-for="m in tas.data.value"
                :key="m.user_id"
                :name="m.name"
                :account="m.account_id"
              >
                <template #actions>
                  <Button
                    variant="ghost-danger"
                    size="icon-sm"
                    :aria-label="t('course.removeTaAria', { name: m.name })"
                    @click="removeTa.ask(m)"
                  >
                    <UserDeleteIcon />
                  </Button>
                </template>
              </MemberCard>
            </div>
          </QueryState>
        </template>
      </section>
    </div>

    <ConfirmDialog
      v-model:open="removeTopic.open"
      :title="t('courses.deleteTitle')"
      :description="t('activity.deleteDescription', { title: removeTopic.target?.title ?? '' })"
      :confirm-text="t('common.ok')"
      destructive
      :loading="removeTopic.isPending"
      :error="removeTopic.error"
      @confirm="removeTopic.confirm()"
    />
    <ConfirmDialog
      v-model:open="removeStudent.open"
      :title="t('course.removeStudentTitle')"
      :description="
        t('course.removeStudentDescription', { name: removeStudent.target?.name ?? '' })
      "
      :confirm-text="t('common.remove')"
      destructive
      :loading="removeStudent.isPending"
      :error="removeStudent.error"
      @confirm="removeStudent.confirm()"
    />
    <ConfirmDialog
      v-model:open="removeTa.open"
      :title="t('course.removeTaTitle')"
      :description="t('course.removeTaDescription', { name: removeTa.target?.name ?? '' })"
      :confirm-text="t('common.remove')"
      destructive
      :loading="removeTa.isPending"
      :error="removeTa.error"
      @confirm="removeTa.confirm()"
    />
    <ConfirmDialog
      v-model:open="confirmTaOpen"
      :title="t('course.addTaTitle')"
      :confirm-text="t('common.add')"
      :loading="addTa.isPending.value"
      :error="taError"
      @confirm="addTa.mutate()"
    >
      <p>{{ t('course.accountLine', { account: taAccount.trim() }) }}</p>
      <p>{{ t('course.nameLine', { name: taName }) }}</p>
    </ConfirmDialog>
  </div>
</template>
