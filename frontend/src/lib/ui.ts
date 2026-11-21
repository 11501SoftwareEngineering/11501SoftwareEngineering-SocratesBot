/**
 * v0.2 頁面共用的 Tailwind class，對應 Figma 的卡片與頁面版型。
 * 注意：根目錄 .gitignore 有 Python 範本的 `lib/`，這個資料夾的新檔案要用 `git add -f` 才會被加進去。
 */

/** 白色圓角卡片（細邊框＋陰影） */
export const cardClass = 'rounded-2xl border-thin border-border bg-card shadow-elevated'

/** 頁面內容區：最寬 1200px、置中 */
export const pageClass = 'mx-auto w-full max-w-[1200px] px-4 pt-[30px] pb-12'
