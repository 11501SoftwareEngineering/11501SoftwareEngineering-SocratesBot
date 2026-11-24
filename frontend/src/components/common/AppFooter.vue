<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
// 頁尾：目前只顯示產品名稱。
// Figma 的「隱私權、版權、開發者、聯絡我們、Bug」還沒有對應的頁面，點了也沒反應，先拿掉；
// 翻譯（footer.*）先留著，做好頁面再加回來並換成 <RouterLink>。
</script>

<template>
  <footer class="shrink-0 bg-secondary px-4 py-2">
    <p class="py-1 text-center font-heading text-footer text-muted-foreground">
      {{ t('common.appName') }}
    </p>
  </footer>
</template>
