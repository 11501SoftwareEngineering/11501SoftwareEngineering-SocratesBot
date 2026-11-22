# 最新 main 的 Gemini 本地版本

基底：`origin/main` 的 `21d4b8f`，本地分支 `local/gemini-main`。
未推送、未部署，也未由代理呼叫真實模型。

## 使用

前端 <http://localhost:5176>；後端 <http://localhost:8003>；
API 文件 <http://localhost:8003/docs>。

使用原老師帳號登入，在原本 AI 設定頁輸入 1–3 把 Gemini API key。
第一欄必填，第二、第三欄可留白。儲存會取代整組金鑰，因此新增第二把時，
請一併重新輸入想保留的第一把。移除會清除整組。所有金鑰均加密儲存，
回應只包含第一把的遮罩，兩把以上會加上 `x2`／`x3`，不會讀回完整金鑰。
支援 AI Studio 的標準與授權型金鑰，不限制必須以 `AIza` 開頭。

模型選單只提供 **Gemini 3.1 Flash-Lite**，原生 ID 為 `gemini-3.1-flash-lite`。
新活動預設使用此模型。歷史非 Gemini 活動不會自動改寫，若要繼續使用，請改選
Gemini 或建立新活動。歷史模型目錄資料保留供既有關聯使用，但不再提供選擇。
價格表沿用 main：顯示 Google 公布的付費文字標準價格（每百萬輸入 US$0.25、
輸出 US$1.50），免費資格及配額以各 Google 專案為準；沒有將未知實際費用填成零。

## 前端範圍

直接使用最新 main 的前端，不沿用先前試驗版的頁面。
必要差異只有老師 AI 設定頁增加兩個相同樣式的密碼欄、傳送多 key 的 API 格式、
原 AI 設定文案改為 Gemini，以及相應測試。沒有供應商選擇、專案 ID、
自訂等待提示或學生頁面變更。main 的最新用量卡片及對話頁修正照常保留。
此分支沒有 Groq 路由、目錄、遷移、介面或 SDK。

## 輪替與限流

validity、status、planning 仍分成三階段，原 milestone 與 schema 驗證保留。
每次階段透過 Redis 共用游標輪替起始金鑰；遇到額度或限流、金鑰拒絕時，
只切換到同一位課程老師的下一把 key。每階段最多三次派送，受原任務時限約束，
每次真正派送都計入用量。沒有其他老師或 OpenRouter 金鑰的自動借用。

Redis 維持有界等待（預設 20 秒、最多 50 個等待者）、滾動每分鐘請求與輸入長度
估算計數、每日計數，以及 429 的 Retry-After／retryDelay 冷卻。
沒有可用金鑰時回傳 503 及 Retry-After，不會無限重送或儲存失敗對話回合。
Redis 不可用時不派送請求。等待是競爭可用配額，並不保證嚴格先進先出。

前端依使用者要求不再輸入 Google 專案 ID，所以本地計數按「金鑰指紋＋模型」
計算，不宣稱能識別金鑰所屬專案。**Google 實際配額仍按專案共享；同專案的三把
key 不會增加額度。** 使用其他應用的流量不包含在本地計數中，Google 回應仍為準。

環境設定：`GEMINI_RPM=15`、`GEMINI_TPM=250000`、`GEMINI_RPD=500`，
請依實際配額調整。後端多程序／多部署需共用 Redis。Redis 資料遺失會失去本地
計數，但 Google 配額不會重置。伺服器端可選用 `GEMINI_API_KEY` 或最多三把
以逗號分隔的 `GEMINI_API_KEYS`；老師有自己的 key 時不會混用伺服器池。

保留 Gemini 專用保守輸入估算與 64,000 對話／128,000 報告預算，避免中文
被誤套用 OpenAI 的 12,000 預算。這些不是實際模型 Token 計數或輸出上限。
三階段輸出上限保持原提示設定，不因 key 數量而增加。

## 本地隔離與驗證

資料庫 `squicrates_gemini_main_local` 為舊 Gemini 本地資料的獨立複本。
已複製老師設定與對話，僅在複本轉換等價 Gemini 模型 ID 及金鑰格式；原資料不變。
舊 Gemini／Groq 測試服務已關閉，舊工作目錄保留供回復，不包含在此分支。
後端紀錄位於工作區 `work/runtime-gemini-main/backend.log`，可見視窗標題為
**Gemini Main Backend Log**。

驗證包含 HTTP mock 的金鑰切換與用量歸屬、真實 Redis 的計量／冷卻／輪替、
真實 PostgreSQL 的三把金鑰加密與老師隔離（測試寫入全部回復），以及既有 session
的三階段離線重播。這些都不呼叫真實模型。實際 Gemini 回覆與專案可用額度仍需實測。

官方參考：[API 相容介面](https://aistudio.google.com/docs/openai)、
[配額](https://aistudio.google.com/docs/rate-limits)、
[模型與價格](https://aistudio.google.com/docs/pricing#gemini-3.1-flash-lite)。
