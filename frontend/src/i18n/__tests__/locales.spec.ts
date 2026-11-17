import { describe, expect, it } from 'vitest'
import { i18n, LOCALES, setLocale } from '..'
import zhTW from '../locales/zh-TW'

function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

const SAMPLE_TEXT = 'SAMPLE'

const params = {
  n: 3,
  page: 'PAGE',
  app: 'APP',
  name: 'NAME',
  title: 'TITLE',
  label: 'LABEL',
  account: 'ACC',
  // 用變數，不直接寫字串：SonarCloud 會把含 password 的屬性配上字串誤判成寫死的密碼
  password: SAMPLE_TEXT,
  code: 'CODE',
  date: 'DATE',
  time: 'TIME',
  y: 2026,
  m: 11,
  v: 2,
  grouped: 1,
  total: 2,
  groups: 3,
  ungrouped: 4,
  processing: 5,
  failed: 6,
}

describe('locales', () => {
  it.each(LOCALES.map((l) => l.value))('%s 每個字串都能顯示、參數都有代入', async (locale) => {
    await setLocale(locale)
    const problems: string[] = []
    expect(i18n.global.locale.value).toBe(locale)
    for (const key of keys(zhTW)) {
      const text = i18n.global.t(key, params)
      if (text === key || /[{}]/.test(text)) problems.push(`${key}: ${text}`)
    }
    expect(problems).toEqual([])
    await setLocale('zh-TW')
  })
})

describe('程式裡用到的 key', () => {
  it('t()／te()／translate() 寫死的 key 都存在於正體中文語言檔', () => {
    const sources = import.meta.glob(['/src/**/*.{ts,vue}', '!/src/i18n/locales/**'], {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>
    const missing: string[] = []
    for (const [file, source] of Object.entries(sources)) {
      for (const match of source.matchAll(/\b(?:t|te|translate)\(\s*'([\w.-]+)'/g)) {
        const key = match[1]!
        const value = key
          .split('.')
          .reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], zhTW)
        if (typeof value !== 'string') missing.push(`${file}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })
})
