<script setup lang="ts">
/**
 * 卡片上的文字連結：主色深的字＋箭頭。對應 Figma「進入課程↗」「檢視觀點↗」「開始探究 →」。
 * stretched：整張卡片都可以點（連結的點擊範圍撐滿最近的 relative 父層）。
 */
import type { RouteLocationRaw } from 'vue-router'

withDefaults(defineProps<{ to: RouteLocationRaw; arrow?: '↗' | '→'; stretched?: boolean }>(), {
  arrow: '↗',
})
</script>

<template>
  <RouterLink
    :to="to"
    class="shrink-0 rounded font-heading text-h2-title whitespace-nowrap text-primary-dark outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
    :class="stretched && 'after:absolute after:inset-0 after:rounded-2xl'"
    ><slot /><span aria-hidden="true">{{ arrow === '→' ? ' →' : '↗' }}</span></RouterLink
  >
</template>
