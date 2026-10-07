<script setup lang="ts"> 
// 對應 Figma Header 元件（node 21:18）。 
// Figma 裡 LOGO 旁邊的文字是「問導魷」，看起來像是設計稿裡先隨便打的暫定字， 
// 這裡先沿用專案原本的正式名稱，並在下面的說明裡請設計師確認要不要改回 Figma 那個名字。 
import { RouterLink } from 'vue-router' 
import { Button } from '@/components/ui/button' 
import { useAuthStore } from '@/stores/auth' 

const authStore = useAuthStore() 
</script> 

<template> 
  <header class="flex h-14 w-full items-center justify-between bg-primary px-4 shadow-sm"> 
    <RouterLink to="/" class="flex items-center gap-2.5"> 
      <span class="size-8 shrink-0 rounded-md bg-background" /> 
      <span class="font-heading text-2xl text-primary-foreground">問導魷</span> 
    </RouterLink> 

    <div v-if="authStore.isAuthenticated" class="flex items-center gap-3"> 
      <span class="text-sm text-primary-foreground">{{ authStore.user?.name }}</span> 
      <span class="rounded-full bg-background/60 px-2 py-0.5 text-xs text-foreground"> 
        {{ authStore.userRole }} 
      </span> 
      <Button variant="secondary" size="sm" @click="authStore.logout()"> 
        登出 
      </Button> 
    </div> 

    <!-- 未登入狀態：註冊與登入切換按鈕 -->
    <div v-else class="flex items-center gap-1.5"> 
      <Button as-child variant="ghost" size="sm"> 
        <RouterLink 
          to="/register" 
          active-class="!bg-[#d6c7b9] hover:!bg-[#c5b5a6] !text-foreground"
          class="text-primary-foreground hover:bg-white/20"
        > 
          註冊 
        </RouterLink> 
      </Button> 
      
      <Button as-child variant="ghost" size="sm"> 
        <RouterLink 
          to="/login" 
          active-class="!bg-[#d6c7b9] hover:!bg-[#c5b5a6] !text-foreground"
          class="text-primary-foreground hover:bg-white/20"
        > 
          登入 
        </RouterLink> 
      </Button> 
    </div> 
  </header> 
</template>