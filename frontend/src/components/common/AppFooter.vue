<script setup lang="ts">
// 對應 Figma Footer 元件（node 21:31）。
// 五個連結目前都還沒有對應的頁面／路由，所以先用純文字呈現，
// 之後哪個組員做好那個頁面，再把對應項目換成 <RouterLink>。
const links = ['隱私權', '版權', '開發者', '聯絡我們', 'Bug']
</script>

<template>
  <footer
    class="flex min-h-10 shrink-0 w-full flex-wrap items-center justify-center gap-x-4 gap-y-2 sm:gap-x-8 bg-secondary px-4 py-2"
  >
    <span
      v-for="link in links"
      :key="link"
      class="cursor-default font-heading text-footer text-foreground"
    >
      {{ link }}
    </span>
  </footer>
</template>
