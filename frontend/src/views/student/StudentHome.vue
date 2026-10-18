<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  useStudentCourses,
  useJoinCourse,
  useLeaveCourse,
  type StudentCourse,
} from '@/api/student'

const searchQuery = ref('')
const isJoinModalOpen = ref(false)
const isLeaveModalOpen = ref(false)

const inputCourseCode = ref('')
const formError = ref('')
const leavingCourse = ref<StudentCourse | null>(null)

// TanStack Query
const { data: courses, isLoading, isError } = useStudentCourses()
const joinMutation = useJoinCourse()
const leaveMutation = useLeaveCourse()

// 搜尋即時過濾
const filteredCourses = computed(() => {
  if (!courses.value) return []
  if (!searchQuery.value.trim()) return courses.value
  const query = searchQuery.value.toLowerCase()
  return courses.value.filter(
    (item) => item.name.toLowerCase().includes(query) || item.code.toLowerCase().includes(query)
  )
})

// 開啟加入課程對話框
const openJoinModal = () => {
  inputCourseCode.value = ''
  formError.value = ''
  isJoinModalOpen.value = true
}

// 提交加入課程
const handleJoinSubmit = () => {
  if (!inputCourseCode.value.trim()) {
    formError.value = '請輸入課程代碼'
    return
  }
  joinMutation.mutate(
    { code: inputCourseCode.value.trim() },
    {
      onSuccess: () => {
        isJoinModalOpen.value = false
      },
    }
  )
}

// 開啟退出課程確認對話框
const openLeaveModal = (item: StudentCourse) => {
  leavingCourse.value = item
  isLeaveModalOpen.value = true
}

// 確認退出課程
const handleLeaveConfirm = () => {
  if (leavingCourse.value) {
    leaveMutation.mutate(leavingCourse.value.id, {
      onSuccess: () => {
        isLeaveModalOpen.value = false
        leavingCourse.value = null
      },
    })
  }
}
</script>

<template>
  <div class="min-h-screen bg-background py-8 px-4">
    <div class="max-w-3xl mx-auto">
      <h1 class="text-2xl font-bold text-foreground mb-6">我的課程</h1>

      <!-- 工具列：搜尋與加入課程按鈕（全面使用 Design Tokens） -->
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
          @click="openJoinModal"
          class="px-4 py-2 bg-primary text-primary-foreground rounded-md shadow-sm hover:opacity-90 transition text-sm font-medium whitespace-nowrap"
        >
          + 加入課程
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
              @click="openLeaveModal(item)"
              class="px-3 py-1.5 bg-destructive/10 text-destructive rounded text-xs font-medium hover:bg-destructive/20 transition"
            >
              退出課程
            </button>
          </div>
        </div>

        <div v-if="filteredCourses.length === 0" class="text-center py-8 text-muted-foreground text-sm">
          目前尚未加入任何課程
        </div>
      </div>

      <!-- 加入課程對話框 (Modal) -->
      <div v-if="isJoinModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-md w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-4 text-foreground">加入課程</h2>
          <div v-if="formError" class="mb-4 text-xs text-destructive">{{ formError }}</div>

          <div class="space-y-4">
            <div>
              <label for="join-code" class="block text-sm font-medium text-foreground mb-1">課程代碼</label>
              <input
                id="join-code"
                v-model="inputCourseCode"
                type="text"
                placeholder="例如：SOC-101"
                class="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground text-sm focus:ring-1 focus:ring-primary uppercase"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <button
              @click="isJoinModalOpen = false"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm hover:opacity-80 transition"
            >
              取消
            </button>
            <button
              @click="handleJoinSubmit"
              class="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition"
            >
              確認加入
            </button>
          </div>
        </div>
      </div>

      <!-- 退出課程確認對話框 (Modal) -->
      <div v-if="isLeaveModalOpen" class="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="bg-card p-6 rounded-lg max-w-sm w-full border border-border shadow-lg">
          <h2 class="text-lg font-bold mb-2 text-foreground">確認退出課程</h2>
          <p class="text-sm text-muted-foreground mb-6">
            確定要退出「{{ leavingCourse?.name }}」嗎？退出後需重新輸入代碼方可加入。
          </p>
          <div class="flex justify-end gap-2">
            <button
              @click="isLeaveModalOpen = false"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md text-sm hover:opacity-80 transition"
            >
              取消
            </button>
            <button
              @click="handleLeaveConfirm"
              class="px-4 py-2 bg-destructive text-destructive-foreground rounded-md text-sm font-medium hover:opacity-90 transition"
            >
              確認退出
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>