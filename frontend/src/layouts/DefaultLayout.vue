<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import AppHeader from '@/components/common/AppHeader.vue'
import AppFooter from '@/components/common/AppFooter.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 頁面重整後,用已保存的 token 重新跟後端確認使用者身分還有效
// (對應 API 規格「取得當前使用者資訊 GET /users/me」的用途)。
onMounted(() => {
  if (authStore.isAuthenticated && !authStore.user) {
    authStore.fetchCurrentUser()
  }
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-neutral-50">
    <AppHeader />

    <main class="container mx-auto flex-1 p-6">
      <RouterView />
    </main>

    <AppFooter />
  </div>
</template>
