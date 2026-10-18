<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  useTeacherCourses,
  useCreateCourse,
  useUpdateCourse,
  useDeleteCourse,
  type TeacherCourse,
} from '@/api/teacher'

const searchQuery = ref('')
const isCreateModalOpen = ref(false)
const isEditModalOpen = ref(false)
const isDeleteModalOpen = ref(false)

const formName = ref('')
const formCode = ref('')
const formError = ref('')

const editingId = ref<number | null>(null)
const deletingCourse = ref<TeacherCourse | null>(null)

// TanStack Query
const { data: courses, isLoading, isError } = useTeacherCourses()
const createMutation = useCreateCourse()
const updateMutation = useUpdateCourse()
const deleteMutation = useDeleteCourse()

// 搜尋即時過濾
const filteredCourses = computed(() => {
  if (!courses.value) return []
  if (!searchQuery.value.trim()) return courses.value
  const query = searchQuery.value.toLowerCase()
  return courses.value.filter(
    (item) => item.name.toLowerCase().includes(query) || item.code.toLowerCase().includes(query)
  )
})

const openCreateModal = () => {
  formName.value = ''
  formCode.value = `CRS-${Date.now().toString().slice(-4)}`
  formError.value = ''
  isCreateModalOpen.value = true
}

// 提交新增
const handleCreateSubmit = () => {
  if (!formName.value.trim()) {
    formError.value = '請填寫課程名稱'
    return
  }
  createMutation.mutate(
    {
      name: formName.value.trim(),
      code: formCode.value.trim(),
    },
    {
      onSuccess: () => {
        isCreateModalOpen.value = false
      },
    }
  )
}

// 開啟編輯課程彈窗
const openEditModal = (item: TeacherCourse) => {
  editingId.value = item.id
  formName.value = item.name
  formCode.value = item.code
  formError.value = ''
  isEditModalOpen.value = true
}

// 提交編輯
const handleEditSubmit = () => {
  if (!formName.value.trim() || editingId.value === null) {
    formError.value = '請填寫課程名稱'
    return
  }
  updateMutation.mutate(
    {
      id: editingId.value,
      name: formName.value.trim(),
      code: formCode.value.trim(),
    },
    {
      onSuccess: () => {
        isEditModalOpen.value = false
        editingId.value = null
      },
    }
  )
}

// 開啟刪除二次確認彈窗
const openDeleteModal = (item: TeacherCourse) => {
  deletingCourse.value = item
  isDeleteModalOpen.value = true
}

// 確認刪除
const handleDeleteConfirm = () => {
  if (deletingCourse.value) {
    deleteMutation.mutate(deletingCourse.value.id, {
      onSuccess: () => {
        isDeleteModalOpen.value = false
        deletingCourse.value = null
      },
    })
  }
}
</script>

<template>
  <div class="min-h-screen bg-background py-8 px-4">
    <div class="max-w-3xl mx-auto">
      <h1 class="text-2xl font-bold text-foreground mb-6">我的課程</h1>

      <!-- 工具列：搜尋與新增按鈕（符合 Design Tokens 規範） -->
      <div class="flex justify-between items-center mb-6 gap-4">
        <div class="relative flex-1">
          <label for="search" class="sr-only">搜尋</label>
          <input
            id="search"
            v-model="searchQuery"
            type="text"
            placeholder="搜尋課程名稱或代碼..."
            class="w-full px-4 py-2 bg-card border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm shadow-sm"
          />
        </div>
        <button
          @click="openCreateModal"
          class="px-4 py-2 bg-primary text-primary-foreground rounded-md shadow-sm hover:opacity-90 transition text-sm font-medium whitespace-nowrap"
        >
          + 新增課程
        </button>
      </div>

      <!-- 狀態提示 -->
      <div v-if="isLoading" class="text-center py-8 text-muted-foreground text-sm">載入中...</div>
      <div v-else-if="isError" class="mb-6 p-4 bg-destructive/10 text-destructive rounded-md text-sm">
        無法載入課程列表資料
      </div>

      <!-- 課程清單 -->
      <div v-else class="space-y-3">
        <div
          v-for="item in filteredCourses"
          :key="item.id"
          class="bg-card p-4 rounded-lg shadow-sm border border-border flex justify-between items-center transition"
        >
          <div>
            <h3 class="text-card-foreground font-medium text-base">{{ item.name }}</h3>
            <p class="text-muted-foreground text-xs mt-1">課程代碼 : {{ item.code }}</p>
          </div>
          <div class="flex gap-2">
            <button
              @click="openEditModal(item)"
              class="px-3 py-1.5 bg-secondary text-secondary-foreground rounded text-xs font-medium hover:opacity-80 transition"
            >
              編輯
            </button>
            <button
              @click="openDeleteModal(item)"
              class="px-3 py-1.5 bg-destructive/10 text-destructive rounded text-xs font-medium hover:bg-destructive/20 transition"
            >
              刪除課程
            </button>
          </div>
        </div>

        <div v-if="filteredCourses.length === 0" class="text-center py-8 text-muted-foreground text-sm">
          沒有符合的課程
        </div>
      </div>

      <!-- 新增課程對話框 (Modal) -->
      <div v-if="isCreateModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-4 text-foreground">新增課程</h2>
          <div v-if="formError" class="mb-4 text-xs text-destructive">{{ formError }}</div>

          <div class="space-y-4">
            <div>
              <label for="create-name" class="block text-sm font-medium text-foreground mb-1">課程名稱</label>
              <input
                id="create-name"
                v-model="formName"
                type="text"
                placeholder="例如：邏輯思考入門"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label for="create-code" class="block text-sm font-medium text-foreground mb-1">課程代碼</label>
              <input
                id="create-code"
                v-model="formCode"
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
              建立課程
            </button>
          </div>
        </div>
      </div>

      <!-- 編輯課程對話框 (Modal) -->
      <div v-if="isEditModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-4 text-foreground">編輯課程</h2>
          <div v-if="formError" class="mb-4 text-xs text-destructive">{{ formError }}</div>

          <div class="space-y-4">
            <div>
              <label for="edit-name" class="block text-sm font-medium text-foreground mb-1">課程名稱</label>
              <input
                id="edit-name"
                v-model="formName"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label for="edit-code" class="block text-sm font-medium text-foreground mb-1">課程代碼</label>
              <input
                id="edit-code"
                v-model="formCode"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <button
              @click="isEditModalOpen = false"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm hover:opacity-80 transition"
            >
              取消
            </button>
            <button
              @click="handleEditSubmit"
              class="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition"
            >
              儲存變更
            </button>
          </div>
        </div>
      </div>

      <!-- 刪除確認對話框 (Modal) -->
      <div v-if="isDeleteModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-sm w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-2 text-foreground">確認刪除課程</h2>
          <p class="text-sm text-muted-foreground mb-6">
            確定要刪除「{{ deletingCourse?.name }}」嗎？此操作無法還原。
          </p>
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
              確定刪除
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>