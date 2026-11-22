<script setup lang="ts">
/**
 * 觀點群組卡片。對應 Figma 元件「Card_Perspective」：
 *   圓點＋群組名稱，右邊「檢視報告↗」（老師才有）
 *   條件說明
 *   大數字人數 + 「/12 (25%)」
 */
import type { RouteLocationRaw } from 'vue-router'
import CardLink from '@/components/common/CardLink.vue'
import { cardClass } from '@/lib/ui'
import { groupColor } from './colors'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  name: string
  conditions: string
  count: number
  total: number
  percentage: number
  index: number
  /** 老師：連到「學生報告」並套用這個群組的 tag */
  to?: RouteLocationRaw
}>()
</script>

<template>
  <article :class="[cardClass, 'flex flex-col gap-2 p-4']">
    <div class="flex items-center justify-between gap-3">
      <h3
        class="flex min-w-0 items-center gap-3 font-heading text-h2-title font-bold text-foreground"
      >
        <span
          class="size-4 shrink-0 rounded-full"
          :style="{ backgroundColor: groupColor(index) }"
          aria-hidden="true"
        />
        <span class="truncate" :title="name">{{ name }}</span>
      </h3>
      <CardLink v-if="to" :to="to" :aria-label="t('report.viewGroupAria', { name })">{{
        t('report.viewGroupReports')
      }}</CardLink>
    </div>
    <p class="text-body-lg text-muted-foreground">{{ conditions }}</p>
    <p class="text-foreground">
      <span class="text-h1-title">{{ count }}</span>
      <span class="ml-1 text-body-lg text-muted-foreground">/{{ total }} ({{ percentage }}%)</span>
    </p>
  </article>
</template>
