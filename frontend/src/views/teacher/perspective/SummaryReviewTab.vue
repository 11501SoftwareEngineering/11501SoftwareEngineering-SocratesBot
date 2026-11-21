<script setup lang="ts">
/**
 * 全班觀點 →「摘要審閱」。對應 Figma「P13-1_Teacher_Result」（node 171:211）：
 *   版本列：草稿／已審閱／已發布 · Ver. 02 · 日期
 *   全班觀點分布：甜甜圈圖、觀點總結（可以直接修改）
 *   觀點群組卡：「檢視報告↗」切到學生報告並套用這個群組的 tag
 *   最下面：☑ 我已確認統計範圍、群組觀點、公開表述與觀點總結。｜撤回發布｜發布摘要
 *
 * 流程（docs/API功能規格.md v0.2「全班報告與摘要」）：
 *   改文字 → 勾「我已確認…」＝ POST /summary/review（帶畫面上的文字，有改就存成新版本）
 *   → 發布摘要 ＝ POST /summary/publish（只發布最新而且已審閱的版本）
 *   勾選後又改文字，勾選會取消，要重新確認。助教（edit_summary）可以改文字、按「儲存修改」（PATCH），不能審閱或發布。
 */
import { computed, ref, watch } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  summariesApi,
  summaryKeys,
  type SummaryStatus,
  type TeacherSummaryResponse,
} from '@/api/summaries'
import AppCheckbox from '@/components/common/AppCheckbox.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { CloseRingIcon, TimeIcon, UploadCircleIcon } from '@/components/icons'
import GroupCard from '@/components/report/GroupCard.vue'
import SummaryOverview from '@/components/report/SummaryOverview.vue'
import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/lib/utils'
import { cardClass } from '@/lib/ui'

const props = defineProps<{
  topicId: string
  data: TeacherSummaryResponse
  canEdit: boolean
  isTeacher: boolean
}>()
const queryClient = useQueryClient()

const summary = computed(() => props.data.summary!)
const text = ref('')
watch(
  () => summary.value.viewpoint_summary,
  (value) => (text.value = value),
  { immediate: true },
)
const dirty = computed(() => text.value.trim() !== summary.value.viewpoint_summary)

const STATUS: Record<SummaryStatus, { label: string; tone: 'primary' | 'secondary' }> = {
  draft: { label: '草稿', tone: 'secondary' },
  reviewed: { label: '已審閱', tone: 'primary' },
  published: { label: '已發布', tone: 'primary' },
  withdrawn: { label: '已撤回', tone: 'secondary' },
}

const error = ref('')
function refresh() {
  void queryClient.invalidateQueries({ queryKey: ['topics', props.topicId, 'summary'] })
  void queryClient.invalidateQueries({ queryKey: summaryKeys.reports(props.topicId) })
}
const payload = () => ({ overview: summary.value.overview, viewpoint_summary: text.value.trim() })
const onError = (fallback: string) => (err: unknown) =>
  (error.value = getApiErrorMessage(err, fallback))

const save = useMutation({
  mutationFn: () => summariesApi.edit(props.topicId, payload()),
  onSuccess: () => ((error.value = ''), refresh()),
  onError: onError('儲存失敗，請稍後再試'),
})
const review = useMutation({
  mutationFn: () => summariesApi.review(props.topicId, payload()),
  onSuccess: () => ((error.value = ''), refresh()),
  onError: onError('確認失敗，請稍後再試'),
})
const publish = useMutation({
  mutationFn: () => summariesApi.publish(props.topicId),
  onSuccess: () => ((error.value = ''), refresh()),
  onError: onError('發布失敗：請先勾選確認，而且要是最新版本'),
})
const withdraw = useMutation({
  mutationFn: () => summariesApi.withdraw(props.topicId),
  onSuccess: () => ((error.value = ''), refresh()),
  onError: onError('撤回失敗，請稍後再試'),
})

const busy = computed(
  () =>
    save.isPending.value ||
    review.isPending.value ||
    publish.isPending.value ||
    withdraw.isPending.value,
)
const reviewed = computed(
  () => !dirty.value && ['reviewed', 'published'].includes(summary.value.summary_status),
)
function toggleReviewed(value: boolean) {
  if (value) review.mutate()
  else if (summary.value.summary_status === 'reviewed') save.mutate()
}
const canPublish = computed(
  () => props.isTeacher && !dirty.value && summary.value.summary_status === 'reviewed',
)

const grouped = computed(() => summary.value.groups.reduce((n, g) => n + g.count, 0))
const meta = computed(
  () =>
    `可用報告：${grouped.value}/${summary.value.denominator} ｜ 觀點群組：${summary.value.groups.length}（未分類：${summary.value.ungrouped_report_ids.length}）`,
)
const date = computed(() =>
  (summary.value.updated_at ?? summary.value.created_at ?? '').slice(0, 10),
)
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center gap-4 text-body-lg text-foreground">
      <StatusTag :tone="STATUS[summary.summary_status].tone">{{
        STATUS[summary.summary_status].label
      }}</StatusTag>
      <span>Ver. {{ String(summary.version).padStart(2, '0') }}</span>
      <span v-if="date" class="flex items-center gap-1"><TimeIcon />{{ date }}</span>
      <span
        v-if="data.published_version && data.published_version !== summary.version"
        class="text-body text-muted-foreground"
      >
        學生目前看到 Ver. {{ String(data.published_version).padStart(2, '0') }}
      </span>
    </div>

    <SummaryOverview
      :counts="summary.groups.map((g) => g.count)"
      :total="summary.denominator"
      :meta="meta"
    >
      <template #text>
        <p class="text-body text-foreground">{{ summary.overview }}</p>
        <p v-if="!canEdit" class="text-body-lg text-muted-foreground">
          {{ summary.viewpoint_summary }}
        </p>
        <label v-if="canEdit" for="viewpoint-summary" class="sr-only">觀點總結</label>
        <textarea
          v-if="canEdit"
          id="viewpoint-summary"
          v-model="text"
          rows="4"
          class="w-full resize-y rounded border border-input bg-background px-2 py-1 text-body-lg text-muted-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
        <div v-if="canEdit && dirty" class="flex items-center gap-3">
          <Button variant="secondary" :disabled="busy" @click="save.mutate()">儲存修改</Button>
          <Button variant="ghost-muted" :disabled="busy" @click="text = summary.viewpoint_summary"
            >還原</Button
          >
        </div>
      </template>
    </SummaryOverview>

    <div class="grid gap-4 md:grid-cols-2">
      <GroupCard
        v-for="(group, i) in summary.groups"
        :key="group.group_id ?? group.name"
        :index="i"
        :name="group.name"
        :conditions="group.conditions"
        :count="group.count"
        :total="summary.denominator"
        :percentage="group.percentage"
        :to="{ query: { tab: 'reports', group: group.group_id ?? group.name } }"
      />
    </div>

    <div
      v-if="isTeacher"
      :class="[
        cardClass,
        'flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between',
      ]"
    >
      <AppCheckbox
        :model-value="reviewed"
        :disabled="busy"
        label="我已確認統計範圍、群組觀點、公開表述與觀點總結。"
        @update:model-value="toggleReviewed"
      />
      <div class="flex justify-end gap-3">
        <Button
          variant="secondary"
          :disabled="busy || !data.published_version"
          @click="withdraw.mutate()"
        >
          <CloseRingIcon /> 撤回發布
        </Button>
        <Button :disabled="busy || !canPublish" @click="publish.mutate()"
          ><UploadCircleIcon /> 發布摘要</Button
        >
      </div>
    </div>
    <p v-if="error" role="alert" class="text-body text-destructive">{{ error }}</p>
  </div>
</template>
