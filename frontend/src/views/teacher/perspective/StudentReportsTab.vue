<script setup lang="ts">
import ViewpointTag from '@/components/common/ViewpointTag.vue'
/**
 * 全班觀點 →「學生報告」。對應 Figma「P13-2_Teacher_Result」（node 724:2527）：
 *   搜尋、「清除 tag」；觀點 tag（摘要的群組）可以點來篩選；「目前 tag：… X 份報告」
 *   表格：姓名、匿名代碼、目前觀點、使用回合數、提交時間、學生報告（檢視）
 * 「檢視」打開那位學生的個人報告（Figma「P13_StudentReport」）。
 * API：GET /topics/{topicId}/reports；觀點 tag 是摘要（GET /topics/{topicId}/summary）的 groups，用 report_ids 對應報告
 */
import { computed, ref, watch } from 'vue'
import type { ReportGroup, TeachingReport, TopicReports } from '@/api/summaries'
import SearchInput from '@/components/common/SearchInput.vue'
import { CloseRingIcon, FileIcon } from '@/components/icons'
import PersonalReport from '@/components/report/PersonalReport.vue'
import { groupColor } from '@/components/report/colors'
import { Button } from '@/components/ui/button'
import { Dialog, DialogScrollContent, DialogTitle } from '@/components/ui/dialog'
import { useSearch } from '@/composables/useSearch'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{ data: TopicReports; groups: ReportGroup[] }>()
const group = defineModel<string>('group', { default: '' })

const current = computed(() => props.groups.find((g) => g.group_id === group.value))
const grouped = computed(() => new Set(props.groups.flatMap((g) => g.report_ids)))

const filtered = computed(() =>
  props.data.reports.filter((r) =>
    !group.value
      ? true
      : group.value === 'ungrouped'
        ? !grouped.value.has(r.report_id)
        : (current.value?.report_ids.includes(r.report_id) ?? false),
  ),
)
const { keyword, results } = useSearch(
  () => filtered.value,
  (r) => [r.student_display_name, r.anonymous_id ?? '', r.final_viewpoint ?? ''],
)

// 照 Prototype：切換或清除 tag 時清空搜尋字詞
watch(group, () => (keyword.value = ''))

const selected = ref<TeachingReport | null>(null)
const open = computed({
  get: () => !!selected.value,
  set: (value: boolean) => {
    if (!value) selected.value = null
  },
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center gap-3">
      <SearchInput v-model="keyword" :label="t('perspective.searchReports')" class="flex-1" />
      <Button variant="secondary" :disabled="!group" @click="group = ''"
        ><CloseRingIcon /> {{ t('perspective.clearTag') }}</Button
      >
    </div>

    <ul v-if="groups.length" class="flex flex-wrap gap-3" :aria-label="t('perspective.tags')">
      <li v-for="(g, i) in groups" :key="g.group_id" class="min-w-0 max-w-[380px]">
        <ViewpointTag
          :label="g.name"
          :color="groupColor(i)"
          :selected="group === g.group_id"
          @click="group = group === g.group_id ? '' : g.group_id"
        />
      </li>
    </ul>
    <p class="flex flex-wrap gap-x-3 text-body text-muted-foreground" role="status">
      <span
        >{{ t('perspective.currentTag')
        }}<b class="font-bold text-foreground">{{ current?.name ?? t('perspective.all') }}</b></span
      >
      <span>{{ t('perspective.reportCount', { n: results.length }) }}</span>
    </p>

    <div class="overflow-x-auto rounded-2xl shadow-elevated">
      <!-- Figma「P13-2」表格：表頭輔色加深 20%、白字 20px 粗體；內容 18px 文字主色；滑過的列底色 #EBE9E1 -->
      <table class="w-full min-w-[760px] border-collapse bg-card text-center text-body-lg">
        <thead class="bg-[#AAA195] text-[20px] font-bold leading-none text-white">
          <tr>
            <th scope="col" class="w-[116px] px-2 py-4">{{ t('perspective.colName') }}</th>
            <th scope="col" class="w-[116px] px-2 py-4">{{ t('perspective.colAnonymous') }}</th>
            <th scope="col" class="px-2 py-4">{{ t('perspective.colViewpoint') }}</th>
            <th scope="col" class="w-[116px] px-2 py-4">{{ t('perspective.colTurns') }}</th>
            <th scope="col" class="w-[146px] px-2 py-4">{{ t('perspective.colSubmitted') }}</th>
            <th scope="col" class="w-[146px] px-2 py-4">{{ t('perspective.colReport') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!results.length">
            <td colspan="6" class="px-3 py-6 text-muted-foreground">
              {{ data.reports.length ? t('perspective.noMatch') : t('perspective.noReports') }}
            </td>
          </tr>
          <tr
            v-for="r in results"
            :key="r.report_id"
            class="border-t-2 border-muted-foreground/40 text-foreground transition-colors hover:bg-border"
            :class="selected?.report_id === r.report_id && 'bg-border'"
          >
            <td class="px-2 py-4">{{ r.student_display_name }}</td>
            <td class="px-2 py-4">{{ r.anonymous_id ?? '—' }}</td>
            <td class="max-w-[490px] truncate px-2 py-4 text-left" :title="r.final_viewpoint ?? ''">
              {{ r.final_viewpoint ?? '—' }}
            </td>
            <td class="px-2 py-4">{{ r.completed_turns }}</td>
            <td class="px-2 py-4">{{ r.completed_at?.slice(0, 10) ?? '—' }}</td>
            <td class="px-2 py-3">
              <Button
                variant="secondary"
                :aria-label="t('perspective.viewAria', { name: r.student_display_name })"
                @click="selected = r"
              >
                <FileIcon /> {{ t('perspective.view') }}
              </Button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="data.processing_count || data.failed_count" class="text-body text-muted-foreground">
      {{
        t('perspective.pending', {
          processing: data.processing_count,
          failed: data.failed_count,
        })
      }}
    </p>

    <Dialog v-model:open="open">
      <DialogScrollContent class="max-w-[883px] bg-card p-6 sm:p-10">
        <DialogTitle class="sr-only">{{
          t('perspective.reportTitle', { name: selected?.student_display_name ?? '' })
        }}</DialogTitle>
        <PersonalReport
          v-if="selected"
          :report="selected"
          :name="selected.student_display_name"
          in-dialog
        />
      </DialogScrollContent>
    </Dialog>
  </div>
</template>
