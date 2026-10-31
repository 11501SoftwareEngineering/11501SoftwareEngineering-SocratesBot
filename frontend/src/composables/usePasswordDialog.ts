import { ref } from 'vue'

// 「修改密碼」對話框掛在 App.vue，Header 的帳號選單用這個打開。
const isOpen = ref(false)

export function usePasswordDialog() {
  return {
    isOpen,
    open: () => (isOpen.value = true),
  }
}
