<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  useTeacherQuestions,
  useCreateQuestion,
  useUpdateQuestion,
  useDeleteQuestion,
  type TeacherQuestion,
} from '@/api/teacher'

const searchQuery = ref('')
const isCreateModalOpen = ref(false)
const isEditModalOpen = ref(false)
const isDeleteModalOpen = ref(false)

const formTitle = ref('')
const formGradeLevel = ref('')
const formRounds = ref(3)
const formTotalCount = ref(30)
const formError = ref('')

const editingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)

// TanStack Query
const { data: questions, isLoading, isError } = useTeacherQuestions()
const createMutation = useCreateQuestion()
const updateMutation = useUpdateQuestion()
const deleteMutation = useDeleteQuestion()

// 搜尋即時過濾
const filteredQuestions = computed(() => {
  if (!questions.value) return []
  if (!searchQuery.value.trim()) return questions.value
  const query = searchQuery.value.toLowerCase()
  return questions.value.filter((item) => item.title.toLowerCase().includes(query))
})

// 開啟新增彈窗
const openCreateModal = () => {
  formTitle.value = ''
  formGradeLevel.value = '7-9'
  formRounds.value = 3
  formTotalCount.value = 30
  formError.value = ''
  isCreateModalOpen.value = true
}

// 提交新增
const handleCreateSubmit = () => {
  if (!formTitle.value.trim()) {
    formError.value = '請填寫問題標題'
    return
  }
  createMutation.mutate(
    {
      title: formTitle.value.trim(),
      grade_level: formGradeLevel.value,
      rounds: Number(formRounds.value),
      total_count: Number(formTotalCount.value),
    },
    {
      onSuccess: () => {
        isCreateModalOpen.value = false
      },
    }
  )
}

// 開啟編輯彈窗
const openEditModal = (item: TeacherQuestion) => {
  editingId.value = item.id
  formTitle.value = item.title
  formGradeLevel.value = item.grade_level
  formRounds.value = item.rounds
  formTotalCount.value = item.total_count
  formError.value = ''
  isEditModalOpen.value = true
}

// 提交編輯
const handleEditSubmit = () => {
  if (!formTitle.value.trim() || editingId.value === null) {
    formError.value = '請填寫問題標題'
    return
  }
  updateMutation.mutate(
    {
      id: editingId.value,
      title: formTitle.value.trim(),
      grade_level: formGradeLevel.value,
      rounds: Number(formRounds.value),
      total_count: Number(formTotalCount.value),
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
const openDeleteModal = (id: number) => {
  deletingId.value = id
  isDeleteModalOpen.value = true
}

// 確認刪除
const handleDeleteConfirm = () => {
  if (deletingId.value !== null) {
    deleteMutation.mutate(deletingId.value, {
      onSuccess: () => {
        isDeleteModalOpen.value = false
        deletingId.value = null
      },
    })
  }
}
</script>

<template>
  <div class="min-h-screen bg-background py-8 px-4">
    <div class="max-w-3xl mx-auto">
      <h1 class="text-2xl font-bold text-foreground mb-6">問題列表</h1>

      <!-- 工具列：搜尋與新增按鈕（已替換為 Design Tokens，無自訂色碼） -->
      <div class="flex justify-between items-center mb-6 gap-4">
        <div class="relative flex-1">
          <label for="search-courses" class="sr-only">搜尋</label>
          <input
            id="search-courses"
            v-model="searchQuery"
            type="text"
            placeholder="搜尋問題..."
            class="w-full px-4 py-2 bg-card border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm shadow-sm"
          />
        </div>
        <button
          @click="openCreateModal"
          class="px-4 py-2 bg-primary text-primary-foreground rounded-md shadow-sm hover:opacity-90 transition text-sm font-medium whitespace-nowrap"
        >
          + 新增問題
        </button>
      </div>

      <!-- 狀態提示 -->
      <div v-if="isLoading" class="text-center py-8 text-muted-foreground text-sm">載入中...</div>
      <div v-else-if="isError" class="mb-6 p-4 bg-destructive/10 text-destructive rounded-md text-sm">
        無法載入問題列表資料
      </div>

      <!-- 問題清單 -->
      <div v-else class="space-y-3">
        <div
          v-for="item in filteredQuestions"
          :key="item.id"
          class="bg-card p-4 rounded-lg shadow-sm border border-border flex justify-between items-center transition"
        >
          <div>
            <h3 class="text-card-foreground font-medium text-base">{{ item.title }}</h3>
            <p class="text-muted-foreground text-xs mt-1">
              年級層 : {{ item.grade_level }} &nbsp;|&nbsp; 回合數 : {{ item.rounds }} &nbsp;|&nbsp; 已完成人數 :
              {{ item.completed_count }}/{{ item.total_count }}
            </p>
          </div>
          <div class="flex gap-2">
            <button
              @click="openEditModal(item)"
              class="px-3 py-1.5 bg-secondary text-secondary-foreground rounded text-xs font-medium hover:opacity-80 transition"
            >
              編輯
            </button>
            <button
              @click="openDeleteModal(item.id)"
              class="px-3 py-1.5 bg-destructive/10 text-destructive rounded text-xs font-medium hover:bg-destructive/20 transition"
            >
              刪除
            </button>
          </div>
        </div>

        <div v-if="filteredQuestions.length === 0" class="text-center py-8 text-muted-foreground text-sm">
          沒有符合的問題
        </div>
      </div>

      <!-- 新增對話框 (Modal) -->
      <div v-if="isCreateModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-4 text-foreground">新增問題</h2>
          <div v-if="formError" class="mb-4 text-xs text-destructive">{{ formError }}</div>

          <div class="space-y-4">
            <div>
              <label for="create-title" class="block text-sm font-medium text-foreground mb-1">問題標題</label>
              <input
                id="create-title"
                v-model="formTitle"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label for="create-grade" class="block text-sm font-medium text-foreground mb-1">年級層</label>
              <input
                id="create-grade"
                v-model="formGradeLevel"
                type="text"
                placeholder="例如：7-9"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="create-rounds" class="block text-sm font-medium text-foreground mb-1">回合數</label>
                <input
                  id="create-rounds"
                  v-model.number="formRounds"
                  type="number"
                  min="1"
                  class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
                />
              </div>
              <div>
                <label for="create-total" class="block text-sm font-medium text-foreground mb-1">總人數</label>
                <input
                  id="create-total"
                  v-model.number="formTotalCount"
                  type="number"
                  min="1"
                  class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
                />
              </div>
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
              建立問題
            </button>
          </div>
        </div>
      </div>

      <!-- 編輯對話框 (Modal) -->
      <div v-if="isEditModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-4 text-foreground">編輯問題</h2>
          <div v-if="formError" class="mb-4 text-xs text-destructive">{{ formError }}</div>

          <div class="space-y-4">
            <div>
              <label for="edit-title" class="block text-sm font-medium text-foreground mb-1">問題標題</label>
              <input
                id="edit-title"
                v-model="formTitle"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label for="edit-grade" class="block text-sm font-medium text-foreground mb-1">年級層</label>
              <input
                id="edit-grade"
                v-model="formGradeLevel"
                type="text"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
              />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="edit-rounds" class="block text-sm font-medium text-foreground mb-1">回合數</label>
                <input
                  id="edit-rounds"
                  v-model.number="formRounds"
                  type="number"
                  min="1"
                  class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
                />
              </div>
              <div>
                <label for="edit-total" class="block text-sm font-medium text-foreground mb-1">總人數</label>
                <input
                  id="edit-total"
                  v-model.number="formTotalCount"
                  type="number"
                  min="1"
                  class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary"
                />
              </div>
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
          <h2 class="text-lg font-bold mb-2 text-foreground">確認刪除</h2>
          <p class="text-sm text-muted-foreground mb-6">確定要刪除這筆問題嗎？此操作無法還原。</p>
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