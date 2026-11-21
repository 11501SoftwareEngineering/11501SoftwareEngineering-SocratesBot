<script setup lang="ts">
/**
 * 統計小卡。對應 Figma P13-1 上方的「完成人數 XX/XX」「可用報告」「觀點群組」：
 * 淺灰底、陰影，左上標題、右上圖示、下面數字。
 */
import type { Component } from 'vue'

defineProps<{ label: string; value: string; icon: Component }>()
</script>

<template>
  <div class="flex flex-col gap-2 rounded-lg bg-border px-3 py-3 shadow-elevated">
    <div class="flex items-center justify-between">
      <dt class="text-body-lg text-foreground">{{ label }}</dt>
      <component :is="icon" aria-hidden="true" />
    </div>
    <dd class="font-heading text-h2-title font-bold text-foreground">{{ value }}</dd>
  </div>
</template>
