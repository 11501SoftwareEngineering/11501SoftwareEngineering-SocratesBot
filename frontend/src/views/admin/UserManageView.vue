<script setup>
import { ref } from 'vue'

// Mock 資料（對應 PM 要求的欄位：id, account, name, created_at）
const teachers = ref([
  { id: 1, account: 'teacher01', name: '王老師', created_at: '2026-03-01' },
  { id: 2, account: 'teacher02', name: '李老師', created_at: '2026-03-02' },
])

const searchQuery = ref('')
const isCreateModalOpen = ref(false)
const isDeleteModalOpen = ref(false)
const newAccount = ref('')
const newName = ref('')
const selectedTeacherId = ref(null)
const errorMessage = ref('')

// 開啟新增對話框
const openCreateModal = () => {
  newAccount.value = ''
  newName.value = ''
  errorMessage.value = ''
  isCreateModalOpen.value = true
}

// 模擬新增老師（使用安全的 crypto API 產生隨機密碼以通過 CodeQL 檢查）
const handleCreate = () => {
  if (!newAccount.value || !newName.value) {
    errorMessage.value = '請填寫帳號與姓名'
    return
  }
  
  // 使用安全的亂數產生方式避免 Insecure randomness (CodeQL 檢查)
  const array = new Uint32Array(1)
  window.crypto.getRandomValues(array)
  const fakePassword = 'pw_' + array[0].toString(36)
  
  teachers.value.push({
    id: Date.now(),
    account: newAccount.value,
    name: newName.value,
    created_at: new Date().toISOString().split('T')[0]
  })
  
  isCreateModalOpen.value = false
  alert(`新增成功！隨機密碼（只會顯示這一次）：${fakePassword}`)
}

// 點擊刪除時先跳出確認對話框
const confirmDelete = (id) => {
  selectedTeacherId.value = id
  isDeleteModalOpen.value = true
}

// 確認刪除
const handleDelete = () => {
  teachers.value = teachers.value.filter(t => t.id !== selectedTeacherId.value)
  isDeleteModalOpen.value = false
  selectedTeacherId.value = null
}
</script>

<template>
  <div class="min-h-screen bg-background py-8 px-4">
    <div class="max-w-3xl mx-auto">
      
      <!-- 頁面主標題 -->
      <h1 class="text-h1-title font-bold text-foreground mb-6">老師管理</h1>

      <!-- 搜尋列與新增按鈕 -->
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
        <button 
          @click="openCreateModal"
          class="px-4 py-2 bg-[#6b8e83] text-white rounded-md shadow-elevated hover:opacity-90 transition text-sm font-medium whitespace-nowrap"
        >
          + 新增教師帳號
        </button>
      </div>

      <!-- 錯誤訊息提示 -->
      <div v-if="errorMessage" class="mb-6 p-4 bg-destructive/10 text-destructive rounded-md shadow-input">
        {{ errorMessage }}
      </div>

      <!-- 教師列表 -->
      <div class="space-y-3">
        <div 
          v-for="teacher in teachers" 
          :key="teacher.id" 
          class="bg-card p-4 rounded-lg shadow-elevated border border-border flex justify-between items-center"
        >
          <div>
            <h3 class="text-card-foreground font-medium text-base">帳號: {{ teacher.account }} (姓名: {{ teacher.name }})</h3>
            <p class="text-muted-foreground text-xs mt-1">建立時間: {{ teacher.created_at }}</p>
          </div>
          <div class="flex gap-2">
            <button 
              @click="confirmDelete(teacher.id)"
              class="px-3 py-1 bg-rose-200 text-rose-700 rounded text-xs hover:bg-rose-300 transition"
            >
              刪除
            </button>
          </div>
        </div>
      </div>

      <!-- 新增教師對話框 (Modal) -->
      <div v-if="isCreateModalOpen" class="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-elevated">
          <h2 class="text-lg font-bold mb-4 text-foreground">建立教師帳號</h2>
          <div class="space-y-4">
            <div>
              <label for="new-account" class="block text-sm font-medium text-foreground mb-1">帳號</label>
              <input id="new-account" v-model="newAccount" type="text" class="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm" />
            </div>
            <div>
              <label for="new-name" class="block text-sm font-medium text-foreground mb-1">姓名</label>
              <input id="new-name" v-model="newName" type="text" class="w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm" />
            </div>
          </div>
          <div class="flex justify-end gap-2 mt-6">
            <button @click="isCreateModalOpen = false" class="px-4 py-2 bg-stone-200 text-stone-700 rounded-md text-sm">取消</button>
            <button @click="handleCreate" class="px-4 py-2 bg-[#6b8e83] text-white rounded-md text-sm">確認新增</button>
          </div>
        </div>
      </div>

      <!-- 刪除確認對話框 (Modal) -->
      <div v-if="isDeleteModalOpen" class="fixed inset-0 bg-black/50 flex items-center justify-center p-4">
        <div class="bg-card p-6 rounded-lg max-w-sm w-full border border-border shadow-elevated">
          <h2 class="text-lg font-bold mb-2 text-foreground">確認刪除</h2>
          <p class="text-sm text-muted-foreground mb-6">確定要刪除這位教師帳號嗎？按確定後將執行刪除。</p>
          <div class="flex justify-end gap-2">
            <button @click="isDeleteModalOpen = false" class="px-4 py-2 bg-stone-200 text-stone-700 rounded-md text-sm">取消</button>
            <button @click="handleDelete" class="px-4 py-2 bg-rose-600 text-white rounded-md text-sm">確定</button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>