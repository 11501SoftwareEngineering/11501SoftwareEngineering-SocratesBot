<script setup lang="ts">
/**
 * 全班觀點分布卡片。對應 Figma P13-1、P08_Student_Result_03 最上面的卡片：
 *   左：甜甜圈圖（中間總人數）
 *   右：「全班觀點分布」＋觀點總結文字（老師的摘要審閱可以直接改，用 #text 插槽放輸入框）
 *   下：可用報告 XX/XX ｜ 觀點群組 XX（未分類 XX）
 */
import DonutChart from './DonutChart.vue'
import { cardClass } from '@/lib/ui'

defineProps<{
  counts: number[]
  total: number
  text?: string
  meta: string
}>()
</script>

<template>
  <section
    :class="[cardClass, 'flex flex-col items-center gap-6 p-6 sm:flex-row sm:items-start']"
    aria-labelledby="class-distribution"
  >
    <DonutChart :counts="counts" :total="total" :label="`全班 ${total} 份報告的觀點分布`" />
    <div class="flex min-w-0 flex-1 flex-col gap-2">
      <h2 id="class-distribution" class="font-heading text-h2-title text-foreground">
        全班觀點分布
      </h2>
      <slot name="text">
        <p class="text-body-lg whitespace-pre-line text-muted-foreground">{{ text }}</p>
      </slot>
      <p class="text-body text-muted-foreground">{{ meta }}</p>
    </div>
  </section>
</template>
