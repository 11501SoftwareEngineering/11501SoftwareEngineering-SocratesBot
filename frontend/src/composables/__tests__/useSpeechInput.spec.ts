import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useSpeechInput } from '../useSpeechInput'

/** 假的瀏覽器語音辨識：測試裡手動丟出辨識結果、錯誤、結束 */
class FakeRecognition {
  static last: FakeRecognition | undefined
  lang = ''
  continuous = false
  interimResults = false
  onresult:
    ((event: { results: { isFinal: boolean; 0: { transcript: string } }[] }) => void) | null = null
  onerror: ((event: { error: string }) => void) | null = null
  onend: (() => void) | null = null
  start = vi.fn<() => void>()
  stop = vi.fn<() => void>(() => this.onend?.())
  abort = vi.fn<() => void>(() => {
    this.onerror?.({ error: 'aborted' })
    this.onend?.()
  })
  constructor() {
    FakeRecognition.last = this
  }
  say(...parts: [string, boolean][]) {
    this.onresult?.({
      results: parts.map(([transcript, isFinal]) => ({ isFinal, 0: { transcript } })),
    })
  }
}

function setup() {
  const texts: string[] = []
  let api!: ReturnType<typeof useSpeechInput>
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useSpeechInput({ onText: (t) => texts.push(t) })
        return () => h('div')
      },
    }),
  )
  return { api, texts, wrapper }
}

describe('useSpeechInput', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    FakeRecognition.last = undefined
  })

  it('瀏覽器不支援時 supported 是 false，按了也不會怎樣', () => {
    vi.stubGlobal('SpeechRecognition', undefined)
    vi.stubGlobal('webkitSpeechRecognition', undefined)
    const { api } = setup()
    expect(api.supported).toBe(false)
    api.toggle()
    expect(api.isListening.value).toBe(false)
  })

  it('用中文辨識，邊說邊把「已確定 + 辨識中」的文字丟出來', () => {
    vi.stubGlobal('webkitSpeechRecognition', FakeRecognition)
    const { api, texts } = setup()
    expect(api.supported).toBe(true)

    api.toggle()
    const r = FakeRecognition.last!
    expect(r.start).toHaveBeenCalled()
    expect(r.lang).toBe('zh-TW')
    expect(r.interimResults).toBe(true)
    expect(api.isListening.value).toBe(true)

    r.say(['我覺得', false])
    r.say(['我覺得要看情況', true], ['因為', false])
    expect(texts).toEqual(['我覺得', '我覺得要看情況因為'])

    api.toggle()
    expect(r.stop).toHaveBeenCalled()
    expect(api.isListening.value).toBe(false)
  })

  it('沒有麥克風權限時顯示錯誤訊息；cancel() 造成的 aborted 不算錯誤', () => {
    vi.stubGlobal('SpeechRecognition', FakeRecognition)
    const { api } = setup()

    api.start()
    FakeRecognition.last!.onerror?.({ error: 'not-allowed' })
    FakeRecognition.last!.onend?.()
    expect(api.errorMessage.value).toContain('麥克風權限')
    expect(api.isListening.value).toBe(false)

    api.start()
    expect(api.errorMessage.value).toBe('')
    api.cancel()
    expect(FakeRecognition.last!.abort).toHaveBeenCalled()
    expect(api.errorMessage.value).toBe('')
    expect(api.isListening.value).toBe(false)
  })

  it('離開頁面時停止辨識', () => {
    vi.stubGlobal('SpeechRecognition', FakeRecognition)
    const { api, wrapper } = setup()
    api.start()
    wrapper.unmount()
    expect(FakeRecognition.last!.abort).toHaveBeenCalled()
  })
})
