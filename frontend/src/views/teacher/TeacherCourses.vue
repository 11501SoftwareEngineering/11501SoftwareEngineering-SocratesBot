<script setup>
import { ref } from 'vue'

const searchQuery = ref('')
// 依照 Figma 老師課程頁面的資料結構
const listData = ref([
  { id: 1, name: '課程名稱', code: '課程代碼: XXXXXXX' },
  { id: 2, name: '課程名稱', code: '課程代碼: XXXXXXX' },
  { id: 3, name: '課程名稱', code: '課程代碼: XXXXXXX' },
])
const errorMessage = ref('')
</script>

<template>
  <!-- 外層置中與最大寬度容器 -->
  <div class="min-h-screen bg-background py-8 px-4">
    <div class="max-w-3xl mx-auto">
      
      <!-- 頁面主標題 -->
      <h1 class="text-h1-title font-bold text-foreground mb-6">我的課程</h1>

      <!-- 搜尋列與新增課程按鈕 -->
      <div class="flex justify-between items-center mb-6 gap-4">
        <div class="relative flex-1">
          <label for="search" class="sr-only">搜尋</label>
          <input 
            id="search"
            v-model="searchQuery" 
            type="text" 
            placeholder="搜尋..." 
            class="w-full px-4 py-2 bg-card border border-border rounded-md shadow-input text-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
          />
        </div>
        <button class="px-4 py-2 bg-[#6b8e83] text-white rounded-md shadow-elevated hover:opacity-90 transition text-sm font-medium whitespace-nowrap">
          + 新增課程
        </button>
      </div>

      <!-- 錯誤訊息提示 -->
      <div v-if="errorMessage" class="mb-6 p-4 bg-destructive/10 text-destructive rounded-md shadow-input">
        {{ errorMessage }}
      </div>

      <!-- 課程列表區塊 -->
      <div class="space-y-3">
        <div 
          v-for="item in listData" 
          :key="item.id" 
          class="bg-card p-4 rounded-lg shadow-elevated border border-border flex justify-between items-center"
        >
          <div>
            <h3 class="text-card-foreground font-medium text-base">{{ item.name }}</h3>
            <p class="text-muted-foreground text-xs mt-1">{{ item.code }}</p>
          </div>
          <div class="flex gap-2">
            <button class="px-3 py-1 bg-stone-200 text-stone-700 rounded text-xs hover:bg-stone-300 transition">編輯</button>
            <button class="px-3 py-1 bg-rose-200 text-rose-700 rounded text-xs hover:bg-rose-300 transition">刪除課程</button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>