import { onBeforeUnmount, ref } from 'vue'
import { i18n, localeInfo, translate } from '@/i18n'

/*
 * TypeScript 內建的型別沒有 SpeechRecognition（各瀏覽器還沒統一），這裡只宣告用得到的部分。
 * 規格：https://developer.mozilla.org/docs/Web/API/SpeechRecognition
 */
interface RecognitionResult {
  readonly isFinal: boolean
  readonly [index: number]: { readonly transcript: string }
}
interface RecognitionEvent {
  readonly results: ArrayLike<RecognitionResult>
}
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: { readonly error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}
type RecognitionConstructor = new () => Recognition

function getRecognition(): RecognitionConstructor | undefined {
  if (typeof window === 'undefined') return undefined
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

// 錯誤代碼 → i18n key（speech.*）
const ERROR_KEYS: Record<string, string> = {
  'not-allowed': 'notAllowed',
  'service-not-allowed': 'notAllowed',
  'audio-capture': 'audioCapture',
  network: 'network',
  'no-speech': 'noSpeech',
  'language-not-supported': 'languageNotSupported',
}
const errorText = (code: string) => translate(`speech.${ERROR_KEYS[code] ?? 'generic'}`)

/**
 * 語音輸入（語音轉文字），全部在前端做，不需要後端 API。
 * 用瀏覽器內建的語音辨識（Web Speech API）：說話時文字會一邊辨識一邊出現。
 *
 * - 支援：Chrome、Edge；Safari 部分支援；Firefox 不支援 → supported = false，不顯示麥克風
 * - Chrome 會把聲音送到 Google 的伺服器辨識，所以需要網路
 *
 * 用法：
 *   const speech = useSpeechInput({ onText: (text) => (draft.value = text) })
 *   speech.toggle()   // 第一次開始聽，第二次停止
 *   speech.cancel()   // 立刻停止，丟掉還沒辨識完的內容（例如按了送出）
 *
 * onText 每次拿到的是「這次開始聽之後說的全部內容」（已確定的 + 還在辨識的），直接覆蓋顯示就好。
 */
export function useSpeechInput(options: { onText: (text: string) => void; lang?: string }) {
  const Recognition = getRecognition()
  const supported = !!Recognition
  const isListening = ref(false)
  const errorMessage = ref('')
  let recognition: Recognition | null = null

  function start() {
    if (!Recognition || recognition) return
    errorMessage.value = ''
    const r = new Recognition()
    // 沒指定就用介面語言（例如介面是日本語就辨識日語）
    r.lang = options.lang ?? localeInfo(i18n.global.locale.value).speech
    r.continuous = true
    r.interimResults = true
    r.onresult = (event) => {
      let text = ''
      for (let i = 0; i < event.results.length; i++) text += event.results[i]?.[0]?.transcript ?? ''
      options.onText(text)
    }
    r.onerror = (event) => {
      // aborted 是我們自己呼叫 cancel()，不是錯誤
      if (event.error !== 'aborted') errorMessage.value = errorText(event.error)
    }
    r.onend = () => {
      isListening.value = false
      recognition = null
    }
    try {
      r.start()
      recognition = r
      isListening.value = true
    } catch {
      errorMessage.value = errorText('')
    }
  }

  /** 停止聽，還沒辨識完的最後一段仍會送到 onText */
  function stop() {
    recognition?.stop()
  }

  /** 立刻停止，丟掉還沒辨識完的內容 */
  function cancel() {
    recognition?.abort()
  }

  function toggle() {
    if (recognition) stop()
    else start()
  }

  onBeforeUnmount(cancel)

  return { supported, isListening, errorMessage, start, stop, cancel, toggle }
}
