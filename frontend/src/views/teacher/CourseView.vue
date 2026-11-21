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
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  courseKeys,
  coursesApi,
  TA_PERMISSIONS,
  type CourseMember,
  type TaPermission,
  type TopicListItem,
} from '@/api/courses'
import { topicsApi } from '@/api/topics'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PageTitle from '@/components/common/PageTitle.vue'
import QueryState from '@/components/common/QueryState.vue'
import SearchInput from '@/components/common/SearchInput.vue'
import SectionHeading from '@/components/common/SectionHeading.vue'
import TabNav from '@/components/common/TabNav.vue'
import ActivityCard from '@/components/course/ActivityCard.vue'
import MemberCard from '@/components/course/MemberCard.vue'
import { AddRingIcon, CopyIcon, TrashIcon, UserDeleteIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useCourse, useCourseTopics } from '@/composables/useCourse'
import { useSearch } from '@/composables/useSearch'
import { getApiErrorMessage } from '@/lib/utils'
import { UserPlus } from '@lucide/vue'

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
const copied = ref(false)
async function copyCode() {
  const code = course.value?.invite_code ?? topicsQuery.data.value?.invite_code
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    copied.value = false
  }
}

// ---------- 探究活動 ----------
const { keyword, results: topics } = useSearch(
  () => topicsQuery.data.value?.topics ?? [],
  (t) => [t.title, t.description ?? ''],
)

function cardFor(topic: TopicListItem) {
  const params = { courseId: courseId.value, topicId: topic.topic_id }
  if (topic.topic_status === 'setup') {
    return {
      status: { label: '草稿', tone: 'secondary' as const },
      link: can('edit_topics')
        ? { label: '繼續編輯', to: { name: 'TeacherActivitySetup', params } }
        : undefined,
      note: can('edit_topics') ? undefined : '草稿待老師確認',
    }
  }
  return {
    status:
      topic.topic_status === 'summary'
        ? { label: '整理摘要中', tone: 'primary' as const }
        : { label: '已發布', tone: 'primary' as const },
    link:
      can('view_reports') || can('edit_summary')
        ? { label: '檢視觀點', to: { name: 'TeacherPerspective', params } }
        : undefined,
    progress: { done: topic.answered_count ?? 0, total: topic.student_count ?? 0 },
  }
}

const removeTopic = useConfirmAction((topic: TopicListItem) => topicsApi.remove(topic.topic_id), {
  onSuccess: () => queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) }),
  errorText: '刪除失敗，請稍後再試',
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
    ? [{ key: 'students' as const, label: '課程成員', count: students.data.value?.length ?? 0 }]
    : []),
  ...(isTeacher.value ? [{ key: 'tas' as const, label: '助教管理' }] : []),
])

function refreshMembers() {
  void queryClient.invalidateQueries({ queryKey: ['courses', courseId.value, 'members'] })
  void queryClient.invalidateQueries({ queryKey: courseKeys.topics(courseId.value) })
}

const removeStudent = useConfirmAction(
  (m: CourseMember) => coursesApi.removeStudent(courseId.value, m.user_id),
  { onSuccess: refreshMembers, errorText: '移除失敗，請稍後再試' },
)
const removeTa = useConfirmAction(
  (m: CourseMember) => coursesApi.removeTa(courseId.value, m.user_id),
  {
    onSuccess: refreshMembers,
    errorText: '移除失敗，請稍後再試',
  },
)

// 新增助教：輸入帳號 →「＋助教」→ 確認視窗 → 送出（預設給全部四項權限，之後可以從卡片修改）
const taAccount = ref('')
/**
 * Figma「P10_AddTA_Confirm」要顯示姓名，但後端沒有「用帳號查使用者」的 API：
 * 本課程學生（改任助教）從學生名單找得到姓名，其他帳號顯示「—」，新增後在助教卡片看到姓名。
 */
const taName = computed(
  () => students.data.value?.find((m) => m.account_id === taAccount.value.trim())?.name ?? '—',
)
const taError = ref('')
const confirmTaOpen = ref(false)
// 照 Figma 沒有權限設定畫面：新增助教時四個權限全開
const DEFAULT_TA_PERMISSIONS = TA_PERMISSIONS.map((p) => p.value)
function askAddTa() {
  taError.value = taAccount.value.trim() ? '' : '請輸入帳號'
  if (!taError.value) confirmTaOpen.value = true
}
const addTa = useMutation({
  mutationFn: () =>
    coursesApi.addTa(courseId.value, taAccount.value.trim(), DEFAULT_TA_PERMISSIONS),
  onSuccess: () => {
    confirmTaOpen.value = false
    taAccount.value = ''
    refreshMembers()
  },
  onError: (err) => (taError.value = getApiErrorMessage(err, '新增失敗，請確認帳號是否正確')),
})

const breadcrumbs = computed(() => [
  {
    label: '我的課程',
    to: { name: 'TeacherCourses' },
  },
])
</script>

<template>
  <div class="mx-auto w-full max-w-[1237px] px-4 pt-[30px] pb-12">
    <PageTitle
      class="lg:px-5"
      :title="course?.name ?? topicsQuery.data.value?.name ?? '課程'"
      :breadcrumbs="breadcrumbs"
      :description="course?.description"
    >
      <template #after-title>
        <span class="flex items-center gap-2 text-header text-foreground">
          課程代碼：{{ course?.invite_code ?? topicsQuery.data.value?.invite_code }}
          <Button
            variant="ghost"
            size="icon-sm"
            :aria-label="copied ? '已複製課程代碼' : '複製課程代碼'"
            @click="copyCode"
          >
            <CopyIcon />
          </Button>
          <span v-if="copied" role="status" class="text-body text-muted-foreground">已複製</span>
        </span>
      </template>
    </PageTitle>

    <div
      class="mt-4 grid items-start gap-8 lg:grid-cols-[minmax(0,774px)_minmax(0,431px)] lg:gap-0"
    >
      <!-- 探究活動 -->
      <section class="flex min-w-0 flex-col gap-2 lg:px-5 lg:py-2">
        <SectionHeading title="探究活動" :count="topicsQuery.data.value?.topics.length ?? 0">
          <template v-if="can('edit_topics')" #actions>
            <Button as-child>
              <RouterLink :to="{ name: 'TeacherNewActivity', params: { courseId } }">
                <AddRingIcon /> 新增活動
              </RouterLink>
            </Button>
          </template>
        </SectionHeading>
        <SearchInput v-model="keyword" label="搜尋探究活動" />
        <QueryState
          :loading="topicsQuery.isPending.value"
          :error="topicsQuery.error.value"
          :empty="topics.length === 0"
          empty-text="找不到探究活動"
          error-text="無法取得探究活動"
          @retry="topicsQuery.refetch()"
        >
          <template v-if="can('edit_topics')" #empty-action>
            試試<RouterLink
              :to="{ name: 'TeacherNewActivity', params: { courseId } }"
              class="rounded underline underline-offset-4 outline-none hover:text-muted-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >新增活動</RouterLink
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
                  variant="ghost"
                  size="icon-sm"
                  :aria-label="`刪除 ${topic.title}`"
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
        aria-label="課程成員與助教"
      >
        <TabNav v-model="panel" :items="panelTabs" label="課程成員與助教" size="lg" />

        <QueryState
          v-if="panel === 'students' && can('view_members')"
          :loading="students.isPending.value"
          :error="students.error.value"
          :empty="(students.data.value?.length ?? 0) === 0"
          empty-text="還沒有學生"
          error-text="無法取得課程成員"
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
                  variant="ghost"
                  size="icon-sm"
                  :aria-label="`移除學生 ${m.name}`"
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
              <label for="ta-account" class="sr-only">助教帳號</label>
              <Input
                id="ta-account"
                v-model="taAccount"
                placeholder="輸入帳號"
                autocomplete="off"
                class="h-9 flex-1 rounded-2xl bg-card"
                :aria-invalid="!!taError"
              />
              <Button type="submit"><UserPlus class="size-6" aria-hidden="true" /> 助教</Button>
            </div>
            <p v-if="taError" role="alert" class="text-body text-destructive">{{ taError }}</p>
          </form>
          <QueryState
            :loading="tas.isPending.value"
            :error="tas.error.value"
            :empty="(tas.data.value?.length ?? 0) === 0"
            empty-text="還沒有助教"
            error-text="無法取得助教名單"
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
                    variant="ghost"
                    size="icon-sm"
                    :aria-label="`移除助教 ${m.name}`"
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
      title="確認刪除?"
      :description="`刪除「${removeTopic.target?.title}」後，學生的對話、報告和全班摘要都會一起刪除，這個動作無法復原。`"
      confirm-text="確認"
      destructive
      :loading="removeTopic.isPending"
      :error="removeTopic.error"
      @confirm="removeTopic.confirm()"
    />
    <ConfirmDialog
      v-model:open="removeStudent.open"
      title="移除學生？"
      :description="`把「${removeStudent.target?.name}」移出這門課，他就看不到課程內容了。`"
      confirm-text="移除"
      destructive
      :loading="removeStudent.isPending"
      :error="removeStudent.error"
      @confirm="removeStudent.confirm()"
    />
    <ConfirmDialog
      v-model:open="removeTa.open"
      title="移除助教？"
      :description="`「${removeTa.target?.name}」之後就不能協助管理這門課。`"
      confirm-text="移除"
      destructive
      :loading="removeTa.isPending"
      :error="removeTa.error"
      @confirm="removeTa.confirm()"
    />
    <ConfirmDialog
      v-model:open="confirmTaOpen"
      title="確定要新增助教？"
      confirm-text="新增"
      :loading="addTa.isPending.value"
      :error="taError"
      @confirm="addTa.mutate()"
    >
      <p>帳號：{{ taAccount.trim() }}</p>
      <p>姓名：{{ taName }}</p>
    </ConfirmDialog>
  </div>
</template>
