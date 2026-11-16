<script setup lang="ts">
import { provide } from 'vue'
import { FORM_FIELD_LAYOUT } from './FormField.vue'
// Figma「P03_Register」「P04_Login」：欄位標籤 32px 粗體、輸入框高 63px、提示 22px（和對話框一樣）
provide(FORM_FIELD_LAYOUT, 'dialog')
// 登入、註冊頁中間的白色卡片（Figma Login / Register）。
</script>

<template>
  <div class="flex justify-center px-4 py-10 sm:py-16">
    <div
      class="w-full max-w-[626px] rounded-2xl border border-border bg-card px-5 py-[27px] shadow-elevated sm:px-[68px]"
    >
      <slot />
    </div>
  </div>
</template>
