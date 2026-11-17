<script setup lang="ts">
/**
 * 探究活動卡片。對應 Figma 元件「Card_Question」（node 783:3252），學生課程頁（P06）、老師課程頁（P10）共用：
 *   第一行：題目（20px），右邊文字連結（檢視觀點↗、繼續編輯↗、開始探究 →…）
 *   第二行：描述
 *   第三行：狀態標籤、年齡層、⏰ 回合數、👥 完成人數＋進度條；右邊放按鈕（刪除）
 */
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { ageBandLabel, type AgeBand } from '@/api/courses'
import CardLink from '@/components/common/CardLink.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import { AlarmClockIcon, GroupIcon } from '@/components/icons'
import { cardClass } from '@/lib/ui'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  title: string
  description?: string | null
  status: { label: string; tone: 'primary' | 'secondary' }
  link?: { label: string; to: RouteLocationRaw; arrow?: '↗' | '→' }
  /** 沒有連結時顯示的說明（例如助教看到「草稿待老師確認」） */
  note?: string
  ageBand?: AgeBand | null
  maxTurns?: number | null
  /** 老師看：完成人數 / 全班人數 */
  progress?: { done: number; total: number }
}>()

const percent = computed(() =>
  props.progress && props.progress.total
    ? Math.min(100, Math.round((props.progress.done / props.progress.total) * 100))
    : 0,
)
</script>

<template>
  <article
    :class="[
      cardClass,
      'relative flex flex-col gap-2 p-4',
      link && 'hover:border-muted-foreground',
    ]"
  >
    <div class="flex flex-col gap-2 py-2">
      <div class="flex items-start justify-between gap-3">
        <h3 class="min-w-0 truncate font-heading text-h2-title text-foreground" :title="title">
          {{ title }}
        </h3>
        <CardLink
          v-if="link && link.arrow !== '→'"
          :to="link.to"
          stretched
          :aria-label="t('common.labelColon', { label: link.label }) + title"
          >{{ link.label }}</CardLink
        >
        <span v-else-if="note" class="shrink-0 text-body text-muted-foreground">{{ note }}</span>
      </div>
      <p
        v-if="description"
        class="truncate text-body-lg text-muted-foreground"
        :title="description"
      >
        {{ description }}
      </p>
    </div>
    <div class="flex min-h-[37px] items-center justify-between gap-3">
      <ul class="flex flex-wrap items-center gap-x-6 gap-y-2 text-body-lg text-foreground">
        <li>
          <StatusTag :tone="status.tone">{{ status.label }}</StatusTag>
        </li>
        <li v-if="ageBand">{{ ageBandLabel(ageBand) }}</li>
        <li v-if="maxTurns" class="flex items-center gap-1">
          <AlarmClockIcon /><span class="sr-only">{{ t('common.turnsLabel') }}</span
          >{{ maxTurns }}
        </li>
        <li v-if="progress" class="flex items-center gap-1">
          <GroupIcon /><span class="sr-only">{{ t('activity.completedCount') }}</span
          >{{ progress.done }}/{{ progress.total }}
          <span
            class="ml-1.5 h-[7px] w-[122px] overflow-hidden rounded-full bg-secondary"
            role="progressbar"
            :aria-valuenow="percent"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="t('activity.completedPercent', { n: percent })"
          >
            <span class="block h-full rounded-full bg-primary" :style="{ width: `${percent}%` }" />
          </span>
        </li>
      </ul>
      <div class="relative z-10 flex items-center gap-1">
        <slot name="actions" />
        <CardLink
          v-if="link && link.arrow === '→'"
          :to="link.to"
          arrow="→"
          stretched
          :aria-label="t('common.labelColon', { label: link.label }) + title"
          >{{ link.label }}</CardLink
        >
      </div>
    </div>
  </article>
</template>
