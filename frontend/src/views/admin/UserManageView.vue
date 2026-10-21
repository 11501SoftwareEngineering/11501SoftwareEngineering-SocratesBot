<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAdminTeachers, useCreateTeacher, useDeleteTeacher } from '@/api/admin'

const searchQuery = ref('')
const isCreateModalOpen = ref(false)
const isDeleteModalOpen = ref(false)
const isPasswordModalOpen = ref(false)

const newAccount = ref('')
const newName = ref('')
const generatedPassword = ref('')
const selectedTeacherId = ref<number | null>(null)
const formError = ref('')

// TanStack Query 串接
const { data: teachers, isLoading, isError } = useAdminTeachers()
const createMutation = useCreateTeacher()
const deleteMutation = useDeleteTeacher()

// 搜尋過濾
const filteredTeachers = computed(() => {
  if (!teachers.value) return []
  if (!searchQuery.value.trim()) return teachers.value
  const query = searchQuery.value.toLowerCase()
  return teachers.value.filter(
    (t) => t.account.toLowerCase().includes(query) || t.name.toLowerCase().includes(query)
  )
})

// 開啟新增對話框
const openCreateModal = () => {
  newAccount.value = ''
  newName.value = ''
  formError.value = ''
  isCreateModalOpen.value = true
}

// 提交新增表單
const handleCreateSubmit = () => {
  if (!newAccount.value.trim() || !newName.value.trim()) {
    formError.value = '請填寫帳號與姓名'
    return
  }
  createMutation.mutate(
    { account: newAccount.value, name: newName.value },
    {
      onSuccess: (data) => {
        isCreateModalOpen.value = false
        generatedPassword.value = data.password
        isPasswordModalOpen.value = true
      },
    }
  )
}

// 開啟刪除確認對話框
const openDeleteModal = (id: number) => {
  selectedTeacherId.value = id
  isDeleteModalOpen.value = true
}

// 確認刪除
const handleDeleteConfirm = () => {
  if (selectedTeacherId.value !== null) {
    deleteMutation.mutate(selectedTeacherId.value, {
      onSuccess: () => {
        isDeleteModalOpen.value = false
        selectedTeacherId.value = null
      },
    })
  }
}
</script>

<template>
  <div class="min-h-screen bg-background py-8 px-4">
    <div class="max-w-3xl mx-auto">
      <!-- 標題 -->
      <h1 class="text-2xl font-bold text-foreground mb-6">老師管理</h1>

      <!-- 工具列：搜尋與新增按鈕 -->
      <div class="flex justify-between items-center mb-6 gap-4">
        <div class="relative flex-1">
          <label for="search" class="sr-only">搜尋</label>
          <div class="relative">
            <span class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input
              id="search"
              v-model="searchQuery"
              type="text"
              placeholder="搜尋..."
              class="w-full pl-9 pr-4 py-2 bg-card border border-border rounded-md shadow-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            />
          </div>
        </div>

        <button
          @click="openCreateModal"
          class="px-4 py-2 bg-primary text-primary-foreground rounded-md shadow-sm hover:opacity-90 transition text-sm font-medium whitespace-nowrap"
        >
          + 新增教師帳號
        </button>
      </div>

      <!-- 狀態提示 -->
      <div v-if="isLoading" class="text-center py-8 text-muted-foreground text-sm">載入中...</div>
      <div v-else-if="isError" class="p-4 mb-6 bg-destructive/10 text-destructive rounded-md text-sm">無法取得教師資料</div>

      <!-- 教師列表 -->
      <div v-else class="space-y-3">
        <div
          v-for="teacher in filteredTeachers"
          :key="teacher.id"
          class="bg-card p-4 rounded-lg shadow-sm border border-border flex justify-between items-center transition"
        >
          <div>
            <h3 class="text-card-foreground font-medium text-base">
              帳號: {{ teacher.account }} <span class="text-muted-foreground text-sm font-normal">(姓名: {{ teacher.name }})</span>
            </h3>
            <p class="text-muted-foreground text-xs mt-1">建立時間: {{ teacher.created_at }}</p>
          </div>
          <div class="flex gap-2">
            <button
              @click="openDeleteModal(teacher.id)"
              class="px-3 py-1.5 bg-destructive/10 text-destructive rounded text-xs font-medium hover:bg-destructive/20 transition"
            >
              刪除
            </button>
          </div>
        </div>

        <div v-if="filteredTeachers.length === 0" class="text-center py-8 text-muted-foreground text-sm">
          沒有符合的教師帳號
        </div>
      </div>

      <!-- 新增教師對話框 (Modal) -->
      <div v-if="isCreateModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-4 text-foreground">建立教師帳號</h2>
          <div v-if="formError" class="mb-4 text-xs text-destructive">{{ formError }}</div>

          <div class="space-y-4">
            <div>
              <label for="new-account" class="block text-sm font-medium text-foreground mb-1">帳號</label>
              <input
                id="new-account"
                v-model="newAccount"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label for="new-name" class="block text-sm font-medium text-foreground mb-1">姓名</label>
              <input
                id="new-name"
                v-model="newName"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <button
              @click="isCreateModalOpen = false"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm hover:opacity-80 transition"
            >
              取消
            </button>
            <button
              @click="handleCreateSubmit"
              class="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition"
            >
              確認新增
            </button>
          </div>
        </div>
      </div>

      <!-- 密碼顯示對話框 (只顯示一次) -->
      <div v-if="isPasswordModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-sm w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-2 text-foreground">帳號建立成功</h2>
          <p class="text-sm text-muted-foreground mb-4">
            以下是系統產生的隨機密碼，<strong class="text-destructive font-semibold">此密碼只會顯示這一次</strong>，請務必複製妥善保存：
          </p>
          <div class="p-3 bg-muted rounded-md text-foreground font-mono text-center text-base tracking-wider mb-6 select-all">
            {{ generatedPassword }}
          </div>
          <div class="flex justify-end">
            <button
              @click="isPasswordModalOpen = false"
              class="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition"
            >
              我已記下密碼
            </button>
          </div>
        </div>
      </div>

      <!-- 刪除確認對話框 (Modal) -->
      <div v-if="isDeleteModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-sm w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-2 text-foreground">確認刪除</h2>
          <p class="text-sm text-muted-foreground mb-6">確定要刪除這位教師帳號嗎？按確定後將執行刪除。</p>
          <div class="flex justify-end gap-2">
            <button
              @click="isDeleteModalOpen = false"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm hover:opacity-80 transition"
            >
              取消
            </button>
            <button
              @click="handleDeleteConfirm"
              class="px-4 py-2 bg-destructive text-destructive-foreground rounded-md text-sm font-medium hover:opacity-90 transition"
            >
              確定
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>