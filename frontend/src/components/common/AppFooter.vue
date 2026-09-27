<script setup lang="ts">
// 對應 Figma Footer 元件（node 21:31）。
// 五個連結目前都還沒有對應的頁面／路由，所以先用純文字呈現，
// 之後哪個組員做好那個頁面，再把對應項目換成 <RouterLink>。
const links = ['隱私權', '版權', '開發者', '聯絡我們', 'Bug']
</script>

<template>
  <footer class="flex h-10 w-full items-center justify-center gap-6 bg-secondary px-4 py-3">
    <span
      v-for="link in links"
      :key="link"
      class="cursor-default font-heading text-sm text-secondary-foreground/80 hover:text-secondary-foreground"
    >
      {{ link }}
    </span>
  </footer>
</template>
