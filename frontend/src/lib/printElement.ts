/**
 * 把畫面上的一個區塊印出來（瀏覽器的列印視窗可以選「另存為 PDF」）。
 *
 * 做法：開一個看不到的 iframe，把目前頁面的樣式表和這個區塊的 HTML 複製進去再列印，
 * 這樣不會印到導覽列、按鈕或對話框外面的頁面。
 * - 文字保持可以選取、搜尋，中日韓文字用的是頁面本來的字型，不用另外打包 PDF 字型
 * - 預設的 PDF 檔名是 title（Chrome、Edge、Safari 都用文件標題當檔名）
 * - 區塊裡加上 print:hidden 的元素（例如匯出按鈕）不會印出來；hidden print:block 的元素只在 PDF 裡出現
 */
export async function printElement(element: HTMLElement, title: string) {
  const iframe = document.createElement('iframe')
  iframe.setAttribute('aria-hidden', 'true')
  iframe.tabIndex = -1
  iframe.style.cssText =
    'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden'
  document.body.appendChild(iframe)

  const doc = iframe.contentDocument
  const win = iframe.contentWindow
  if (!doc || !win) {
    iframe.remove()
    return
  }

  const styles = [...document.querySelectorAll('style, link[rel="stylesheet"]')]
    .map((node) => node.outerHTML)
    .join('')
  doc.open()
  doc.write(
    `<!doctype html><html lang="${document.documentElement.lang}"><head><meta charset="utf-8">` +
      `<title>${escapeHtml(title)}</title>${styles}` +
      // A4、留白；背景色（標籤、紅框）照樣印出來
      '<style>@page{size:A4;margin:16mm}html,body{background:#fff!important}' +
      'body{-webkit-print-color-adjust:exact;print-color-adjust:exact}</style>' +
      `</head><body>${element.outerHTML}</body></html>`,
  )
  doc.close()

  // 等樣式表和字型載入完，不然會印出沒有樣式的版本
  await Promise.all(
    [...doc.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')].map(
      (link) =>
        new Promise<void>((resolve) => {
          if (link.sheet) return resolve()
          link.addEventListener('load', () => resolve(), { once: true })
          link.addEventListener('error', () => resolve(), { once: true })
        }),
    ),
  )
  await doc.fonts?.ready

  const pageTitle = document.title
  document.title = title
  const cleanup = () => {
    document.title = pageTitle
    iframe.remove()
  }
  // 列印視窗關掉才會觸發；有些手機瀏覽器 print() 不會等，所以另外保底一分鐘後清掉
  win.addEventListener('afterprint', cleanup, { once: true })
  setTimeout(() => iframe.isConnected && cleanup(), 60_000)
  win.focus()
  win.print()
}

function escapeHtml(text: string) {
  return text.replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  )
}
