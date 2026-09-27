<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppFooter from '@/components/common/AppFooter.vue'
import AppHeader from '@/components/common/AppHeader.vue'

// Figma 的 Home / Login 兩個畫面都共用同一個 Header + Footer，
// 所以先直接包在最外層的 App.vue。之後頁面變多、需要不同版型（例如老師/學生
// 有不同的側邊欄）時，再抽成 src/layouts/ 底下的版型元件會比較好維護。
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background">
    <AppHeader />
    <main class="flex-1">
      <!-- RouterView 就像是投影幕，當前網址對應到的 View（如 LoginView）會被投射在這裡 -->
      <RouterView />
    </main>
    <AppFooter />
  </div>
</template>
