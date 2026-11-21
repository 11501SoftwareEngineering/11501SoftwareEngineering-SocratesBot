import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'
import { onBeforeRouteLeave, useRouter, type RouteLocationRaw } from 'vue-router'

/**
 * 「還沒儲存，確定要離開？」（Figma「P11_Confirm」）。
 * 有未儲存的修改時：站內換頁先問；關閉分頁、重新整理由瀏覽器問。
 *
 *   const guard = useUnsavedGuard(isDirty)
 *   <ConfirmDialog v-model:open="guard.open.value" … @confirm="guard.leave()" />
 */
export function useUnsavedGuard(dirty: Ref<boolean>) {
  const router = useRouter()
  const open = ref(false)
  let target: RouteLocationRaw | null = null
  let allowed = false

  onBeforeRouteLeave((to) => {
    if (allowed || !dirty.value) return true
    target = to.fullPath
    open.value = true
    return false
  })

  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (dirty.value) event.preventDefault()
  }
  onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

  /** 確定離開 */
  function leave() {
    open.value = false
    allowed = true
    if (target) void router.push(target)
  }

  /** 儲存完、發布完要換頁時，不要再問 */
  function allow() {
    allowed = true
  }

  return { open, leave, allow }
}
