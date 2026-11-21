<script setup lang="ts">
/**
 * 探索結果報告 →「全班摘要」分頁。對應 Figma「P08_Student_Result_03」（node 787:2744）。
 * API：GET /topics/{topicId}/summary/published（老師發布後才有；沒有姓名、匿名代碼、原話）
 */
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { summariesApi, summaryKeys } from '@/api/summaries'
import ComingSoon from '@/components/common/ComingSoon.vue'
import QueryState from '@/components/common/QueryState.vue'
import GroupCard from '@/components/report/GroupCard.vue'
import SummaryOverview from '@/components/report/SummaryOverview.vue'

const props = defineProps<{ topicId: string }>()

const { data, isPending, error, refetch } = useQuery({
  queryKey: computed(() => summaryKeys.published(props.topicId)),
  queryFn: () => summariesApi.published(props.topicId),
  enabled: () => !!props.topicId,
})

const meta = computed(() => {
  const s = data.value
  if (!s) return ''
  const grouped = s.denominator - s.ungrouped_count
  return `可用報告：${grouped}/${s.denominator} ｜ 觀點群組：${s.groups.length}（未分類：${s.ungrouped_count}）`
})
</script>

<template>
  <QueryState :loading="isPending" :error="error" error-text="無法取得全班摘要" @retry="refetch()">
    <ComingSoon v-if="!data" title="老師還沒有發布全班摘要">
      全班都完成之後，老師整理好就會在這裡看到大家的想法。
    </ComingSoon>
    <div v-else class="flex flex-col gap-4">
      <SummaryOverview
        :counts="data.groups.map((g) => g.count)"
        :total="data.denominator"
        :text="[data.overview, data.viewpoint_summary].filter(Boolean).join('\n')"
        :meta="meta"
      />
      <div class="grid gap-4 md:grid-cols-2">
        <GroupCard
          v-for="(group, i) in data.groups"
          :key="group.name"
          :index="i"
          :name="group.name"
          :conditions="group.conditions"
          :count="group.count"
          :total="data.denominator"
          :percentage="group.percentage"
        />
      </div>
    </div>
  </QueryState>
</template>
