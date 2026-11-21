import { ref } from 'vue'

/** 目前正在朗讀哪一則（同一時間只會唸一則），所有 useSpeech 共用 */
const speakingId = ref<string | null>(null)

/**
 * 朗讀文字：用瀏覽器內建的語音（Web Speech API），不需要後端。
 * 對應 Figma 對話紀錄裡 AI 訊息下方的喇叭圖示。
 *
 * 用法：
 *   const { supported, isSpeaking, toggle } = useSpeech()
 *   toggle('m1', '要唸的文字')
 *
 * 瀏覽器不支援（supported = false）時，畫面上就不顯示喇叭按鈕。
 */
export function useSpeech(lang = 'zh-TW') {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window

  function stop() {
    if (!supported) return
    window.speechSynthesis.cancel()
    speakingId.value = null
  }

  function speak(id: string, text: string) {
    if (!supported) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.onend = utterance.onerror = () => {
      if (speakingId.value === id) speakingId.value = null
    }
    speakingId.value = id
    window.speechSynthesis.speak(utterance)
  }

  function toggle(id: string, text: string) {
    if (speakingId.value === id) stop()
    else speak(id, text)
  }

  const isSpeaking = (id: string) => speakingId.value === id

  return { supported, isSpeaking, toggle, stop }
}
