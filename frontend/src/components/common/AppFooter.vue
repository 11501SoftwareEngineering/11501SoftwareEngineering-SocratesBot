<script setup lang="ts">
// 頁尾。電腦版一排（Figma Footer），手機版直排加分隔線（Figma Footer_phone）。
const links = ['隱私權', '版權', '開發者', '聯絡我們', 'Bug']
</script>

<template>
  <footer class="shrink-0 bg-secondary px-4 py-2">
    <ul
      class="mx-auto flex max-w-md flex-col divide-y divide-muted-foreground/60 px-4 sm:max-w-none sm:flex-row sm:flex-wrap sm:items-center sm:justify-center sm:gap-x-8 sm:divide-y-0 sm:px-0"
    >
      <li
        v-for="link in links"
        :key="link"
        class="py-3 text-center font-heading text-footer text-muted-foreground sm:py-0"
      >
        <a
          v-if="link === 'Bug'"
          href="https://docs.google.com/forms/d/e/1FAIpQLSfQhV0xEnduCiiWKDeWuTVTVr2aVeOE8QfzCPDg2GaDmg0cDQ/viewform"
          class="hover:underline focus-visible:underline"
        >
          {{ link }}
        </a>
        <template v-else>{{ link }}</template>
      </li>
    </ul>
  </footer>
</template>
