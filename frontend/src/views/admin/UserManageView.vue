<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  useAdminTeachers,
  useCreateTeacher,
  useResetTeacherPassword,
  useDeleteTeacher,
} from '@/api/admin'

const searchQuery = ref('')
const isCreateModalOpen = ref(false)
const isDeleteModalOpen = ref(false)

const newAccount = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const errorMessage = ref('')
const selectedTeacherId = ref<number | null>(null)

// TanStack Query
const { data: teachers, isLoading, isError } = useAdminTeachers()
const createMutation = useCreateTeacher()
const resetPasswordMutation = useResetTeacherPassword()
const deleteMutation = useDeleteTeacher()

// 搜尋過濾
const filteredTeachers = computed(() => {
  if (!teachers.value) return []
  if (!searchQuery.value.trim()) return teachers.value
  const query = searchQuery.value.toLowerCase()
  return teachers.value.filter((t) => t.account.toLowerCase().includes(query))
})

// 開啟建立教師帳號彈窗 (AddTeacher)
const openCreateModal = () => {
  newAccount.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  errorMessage.value = ''
  isCreateModalOpen.value = true
}

// 提交新增教師帳號
const handleCreateSubmit = () => {
  if (!newAccount.value.trim() || !newPassword.value.trim()) {
    errorMessage.value = '錯誤訊息'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = '錯誤訊息'
    return
  }
  createMutation.mutate(
    {
      account: newAccount.value.trim(),
      password: newPassword.value.trim(),
    },
    {
      onSuccess: () => {
        isCreateModalOpen.value = false
      },
    }
  )
}

// 重設密碼
const handleResetPassword = (id: number) => {
  resetPasswordMutation.mutate(id)
}

// 開啟刪除確認彈窗 (Comfire)
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
  <div class="bg-background py-10 px-4">
    <div class="max-w-2xl mx-auto">
      <!-- 頁面標題 (對齊 Figma 樣板大小與間距) -->
      <h1 class="text-header font-bold text-foreground mb-4">老師管理</h1>

      <!-- 工具列：搜尋框 + 新增老師按鈕 -->
      <div class="flex justify-between items-center mb-4 gap-3">
        <div class="relative flex-1">
          <label for="search" class="sr-only">搜尋</label>
          <span class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input
            id="search"
            v-model="searchQuery"
            type="text"
            placeholder="搜尋"
            class="w-full h-7 pl-8 pr-8 bg-card border border-border rounded-full shadow-input text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring text-body"
          />
          <!-- 永遠顯示的 ⊗ 清除圖示 (完全對齊 Figma 樣板) -->
          <button
            type="button"
            @click="searchQuery = ''"
            class="absolute inset-y-0 right-0 flex items-center pr-2 text-muted-foreground hover:text-foreground"
            aria-label="清除搜尋"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" stroke-width="1.8" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M15 9l-6 6m0-6l6 6" />
            </svg>
          </button>
        </div>

        <!-- 新增老師按鈕 (與搜尋框同高 h-7) -->
        <button
          type="button"
          @click="openCreateModal"
          class="h-7 px-3 bg-primary text-primary-foreground rounded-md shadow-elevated hover:opacity-90 transition text-h2-title font-medium flex items-center gap-1.5 whitespace-nowrap"
        >
          <span>新增老師</span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="9" stroke-width="2" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v8m-4-4h8" />
          </svg>
        </button>
      </div>

      <!-- 狀態提示 -->
      <div v-if="isLoading" class="text-center py-8 text-muted-foreground text-h2-title">載入中...</div>
      <div v-else-if="isError" class="p-4 mb-6 bg-destructive/20 text-foreground rounded-md text-h2-title">無法取得教師資料</div>

      <!-- 教師卡片清單 -->
      <div v-else class="space-y-3.5">
        <div
          v-for="teacher in filteredTeachers"
          :key="teacher.id"
          class="bg-card px-5 py-3.5 rounded-xl shadow-elevated border border-border flex justify-between items-center"
        >
          <div>
            <h3 class="text-card-foreground font-medium text-h2-title">
              帳號: {{ teacher.account }}
            </h3>
            <p class="text-muted-foreground text-body mt-0.5">
              預設密碼: {{ teacher.defaultPassword }}
            </p>
          </div>

          <div class="flex items-center gap-2.5">
            <!-- 重設密碼按鈕 (字級 text-h2-title 16px、單箭頭重整圖示) -->
            <button
              type="button"
              @click="handleResetPassword(teacher.id)"
              class="px-2.5 py-0.5 bg-secondary text-secondary-foreground rounded-md shadow-elevated hover:opacity-90 transition text-h2-title font-medium flex items-center gap-1.5"
            >
              <span>重設密碼</span>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M4.5 9A8 8 0 1 1 6 17.5" />
              </svg>
            </button>

            <!-- 刪除按鈕 (字級 text-h2-title 16px、實心珊瑚紅底) -->
            <button
              type="button"
              @click="openDeleteModal(teacher.id)"
              class="px-2.5 py-0.5 bg-destructive text-foreground rounded-md shadow-elevated hover:opacity-90 transition text-h2-title font-medium flex items-center gap-1.5"
            >
              <span>刪除</span>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="filteredTeachers.length === 0" class="text-center py-8 text-muted-foreground text-h2-title">
          沒有符合的教師帳號
        </div>
      </div>

      <!-- 建立教師帳號彈窗 (Figma: AddTeacher) -->
      <div v-if="isCreateModalOpen" class="fixed inset-0 bg-foreground/20 backdrop-blur-[1px] flex items-center justify-center p-4 z-50">
        <div class="bg-card px-8 py-7 rounded-xl max-w-md w-full border border-border shadow-elevated">
          <h2 class="text-header font-bold mb-6 text-foreground text-center">建立教師帳號</h2>

          <div class="space-y-4">
            <!-- 帳號名稱 -->
            <div>
              <div class="flex items-center gap-3">
                <label for="new-account" class="text-h2-title font-medium text-foreground whitespace-nowrap w-20">帳號名稱：</label>
                <input
                  id="new-account"
                  v-model="newAccount"
                  type="text"
                  class="flex-1 px-3 py-1 border border-border rounded bg-background text-foreground text-h2-title shadow-input focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <p class="text-body text-muted-foreground text-right mt-1">提示訊息</p>
            </div>

            <!-- 建立密碼 -->
            <div>
              <div class="flex items-center gap-3">
                <label for="new-password" class="text-h2-title font-medium text-foreground whitespace-nowrap w-20">建立密碼：</label>
                <input
                  id="new-password"
                  v-model="newPassword"
                  type="password"
                  class="flex-1 px-3 py-1 border border-border rounded bg-background text-foreground text-h2-title shadow-input focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <p class="text-body text-muted-foreground text-right mt-1">提示訊息</p>
            </div>

            <!-- 確認密碼 -->
            <div>
              <div class="flex items-center gap-3">
                <label for="confirm-password" class="text-h2-title font-medium text-foreground whitespace-nowrap w-20">確認密碼：</label>
                <input
                  id="confirm-password"
                  v-model="confirmPassword"
                  type="password"
                  class="flex-1 px-3 py-1 border border-border rounded bg-background text-foreground text-h2-title shadow-input focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <p v-if="errorMessage" class="text-body text-destructive text-right mt-1">{{ errorMessage }}</p>
              <p v-else class="text-body text-destructive text-right mt-1">錯誤訊息</p>
            </div>
          </div>

          <div class="flex justify-end gap-3 mt-6">
            <button
              type="button"
              @click="isCreateModalOpen = false"
              class="px-4 py-1 bg-secondary text-secondary-foreground rounded shadow-elevated text-h2-title font-medium hover:opacity-90 transition"
            >
              取消
            </button>
            <button
              type="button"
              @click="handleCreateSubmit"
              class="px-4 py-1 bg-primary text-primary-foreground rounded shadow-elevated text-h2-title font-medium hover:opacity-90 transition"
            >
              新增
            </button>
          </div>
        </div>
      </div>

      <!-- 刪除確認彈窗 (Figma: Comfire) -->
      <div v-if="isDeleteModalOpen" class="fixed inset-0 bg-foreground/20 backdrop-blur-[1px] flex items-center justify-center p-4 z-50">
        <div class="bg-card px-6 py-6 rounded-xl max-w-xs w-full border border-border shadow-elevated text-center">
          <h2 class="text-header font-bold mb-3 text-foreground">確認刪除?</h2>
          <p class="text-h2-title text-foreground mb-5 leading-relaxed">
            說明說明說明說明<br />說明說明說明說明
          </p>
          <div class="flex justify-center gap-3">
            <button
              type="button"
              @click="isDeleteModalOpen = false"
              class="px-4 py-1 bg-secondary text-secondary-foreground rounded shadow-elevated text-h2-title font-medium hover:opacity-90 transition"
            >
              取消
            </button>
            <button
              type="button"
              @click="handleDeleteConfirm"
              class="px-4 py-1 bg-destructive text-foreground rounded shadow-elevated text-h2-title font-medium hover:opacity-90 transition"
            >
              確認
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>