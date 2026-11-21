<script setup lang="ts">
/**
 * 甜甜圈圖：全班觀點分布。對應 Figma P13-1、P08_Student_Result_03 左邊的圓環，中間是總人數。
 * 用 SVG 畫，每一段的顏色跟下面的群組卡片圓點一樣（groupColor）。
 */
import { computed } from 'vue'
import { groupColor } from './colors'

const props = defineProps<{ counts: number[]; total: number; label: string }>()

const R = 40
const C = 2 * Math.PI * R
const segments = computed(() => {
  const sum = props.counts.reduce((a, b) => a + b, 0) || 1
  let offset = 0
  return props.counts.map((count, i) => {
    const length = (count / sum) * C
    const segment = { color: groupColor(i), dash: `${length} ${C - length}`, offset: -offset }
    offset += length
    return segment
  })
})
</script>

<template>
  <figure class="relative size-[135px] shrink-0" :aria-label="label">
    <svg viewBox="0 0 100 100" class="size-full -rotate-90" aria-hidden="true">
      <circle cx="50" cy="50" :r="R" fill="none" class="stroke-border" stroke-width="13" />
      <circle
        v-for="(s, i) in segments"
        :key="i"
        cx="50"
        cy="50"
        :r="R"
        fill="none"
        :stroke="s.color"
        stroke-width="13"
        :stroke-dasharray="s.dash"
        :stroke-dashoffset="s.offset"
      />
    </svg>
    <figcaption
      class="absolute inset-0 flex items-center justify-center text-h1-title text-foreground"
    >
      {{ total }}
    </figcaption>
  </figure>
</template>
