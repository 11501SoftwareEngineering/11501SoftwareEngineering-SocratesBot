# AI 聊天串接（本機驗證）

本功能只實作既有學生聊天頁的即時對話 API，沒有原型前端、教師八欄設定、個人報告或全班分類。
登入、課程與題目沿用原前端 MSW 測試資料；正式 main 後端與資料庫維持原樣，尚未整合 main JWT／課程權限。

## 啟動與檢查

需要 Node.js 24.12 以上與網路連線。在儲存庫根目錄執行：

    npm run setup

填入 ai/.env.local 的 OPENROUTER_API_KEY；模型預設 openai/gpt-4.1-mini，須支援 JSON Schema 與串流。金鑰只放伺服器環境變數，請勿提交 Git。

    npm run dev

開啟 http://127.0.0.1:5180/login，使用 s012／password123，選哲學概論 → 善意的謊言是對的嗎？
Ctrl+C 同時關閉兩個服務。連接埠在 chat.config.json 設定；不需要啟動 Python、Postgres 或 make。

    npm run check

檢查 AI 型別與 11 項測試，以及前端 lint、變動檔案格式、型別、單元測試與建置，不需要 API 金鑰。
npm run dev:mock 只展示原始假對話。frontend/ 內原有指令與 CI 維持原樣。

本功能只在 VITE_CHAT_API_ENABLED=true 啟用；根目錄 dev 會設定此旗標與 VITE_CHAT_API_URL。
ai/.gitignore 包含 lib/ 的例外規則，避免根目錄原有 Python 忽略規則漏掉 TypeScript AI 核心；node_modules 與實際金鑰檔仍排除。

## PR 關係

截至 2026-11-17，PR205 尚未合併：
https://github.com/11501SoftwareEngineering/11501SoftwareEngineering-SocratesBot/pull/205

本 PR 以 main 為基底，只改既有 ChatView、useChatStream 並新增 chat.ts，不重送 PR205 原本的報告分頁與共用元件。聊天功能可以獨立審查，PR205 的 UI 變更仍由該 PR 合併。
原交付版已在 PR205 頁面收到兩次真實模型回覆。PR 整理僅調整儲存庫路徑、可攜的啟動指令、Git 忽略規則與 AI 測試 CI。

## 資料流

1. PR205 原本的測試登入、課程與題目 API 由原有 MSW 處理。
2. ChatView 讀取選定題目的標題、描述、年齡範圍及回合數。
3. 新 chat.ts 呼叫獨立 AI 服務建立對話，不呼叫 main 的 Session API。
4. 學生送訊息後，AI 服務先執行 prototype 原有的回答有效性判斷，再呼叫原有對話提示詞。
5. 從模型回傳的結構化 JSON 串流中，只提取 studentMessage 的文字片段，透過 SSE 傳給原 PR205 氣泡。進度資料、有效性判斷說明不送到學生畫面。
6. 完整回覆通過原型 schema 後，保存學生訊息、AI 訊息與進度，再發出 done。前端重新取得正式紀錄與剩餘回合。

本版使用 /chat-api/v1 路徑，以避開 PR205 原有 MSW 的 /api/v1 攔截。預設前端 http://127.0.0.1:5180、AI http://127.0.0.1:8008。AI 只監聽本機。

## 本版 API

### GET /health

確認服務存活，回傳 service、status、ai_configured、model。ai_configured 只表示有填寫金鑰，不表示已驗證金鑰或額度。

### POST /chat-api/v1/sessions

輸入（沿用 PR205 的現成題目）：

    {
      "topic_id": "t-lie",
      "title": "善意的謊言是對的嗎？",
      "description": "題目說明，可省略",
      "age_range": "13-15",
      "max_rounds": 5
    }

age_range 可為 13-15、16-18、18+；省略時採 16-18。
max_rounds 可為 1–15；省略時採 5。開場白由標題直接組成，不呼叫 AI。

成功 201：session_id、topic_id、session_token。
session_token 為隨機產生的本對話存取憑證，之後兩支 API 必須帶 Authorization: Bearer <session_token>。
這不是 main 的 JWT，不代表已經完成正式帳號／課程權限整合。本機測試的帳號只用於前端區分暫存紀錄。

### GET /chat-api/v1/sessions/{sessionId}/messages

成功 200：

    {
      "session_id": "...",
      "topic_id": "t-lie",
      "status": "IN_PROGRESS",
      "max_rounds": 5,
      "remaining_rounds": 5,
      "messages": [
        {"message_id": "...", "role": "assistant", "content": "開場訊息"}
      ]
    }

欄位對齊 PR205 的 SessionMessages 型別；完成時 status 為 COMPLETED。
可在重新整理、串流失敗後用這支 API 校準。

### POST /chat-api/v1/sessions/{sessionId}/messages/stream

輸入：

    {"content": "學生回答", "request_id": "由前端產生的 UUID"}

content 須去除首尾空白後為 1–2000 字，沿用 prototype 的限制。
成功以 text/event-stream 回傳：

    event: data
    data: "你會如何"

    event: data
    data: "區分這兩種情況？"

    event: done
    data: {"message_id":"...","is_guiding_question":true,"remaining_rounds":4,"is_completed":false}

data 的內容是 JSON 字串，前端解碼後接在上一段後方，保留換行。
資料尚未傳完時的氣泡文字屬於暫時內容；只有 done 才代表完整驗證與保存成功。

AI 或有效性判斷失敗，在串流中回傳：

    event: error
    data: {"status":422,"detail":"這則回答未通過原型的有效性檢查……"}

這時不保存該回合，前端還原輸入並重讀既有紀錄，不會拿假回覆代替 AI。
SSE 開始後 HTTP 狀態已是 200，錯誤狀態放在 error 事件裡；請勿只檢查 HTTP 200。

串流開始前的錯誤：欄位錯誤 422、無憑證／憑證錯誤 403、Session 不存在 404、已結束 400、同時有其他回合／request_id 內容衝突 409。
AI 服務失敗回 502／503，逾時回 504（串流內 error）。

## 回合與重試

- 一組「有效學生回答 + 完整 AI 回覆」算一回合；開場白不扣回合。
- 同一 Session 同時只接受一則生成請求。
- 同 request_id、同內容且已成功：回放原結果，不重複呼叫模型、不重複保存、不再扣回合。
- 同 request_id、不同內容：409。
- 未成功的請求允許重試；不保證供應商對失敗或中斷的呼叫免計費。
- 達到 PR205 的回合上限，或 prototype 回傳 student_requested_stop／safety_interruption 時，對話標成 COMPLETED。自然語言要求停止是否被判定，仍取決於原型模型；本版沒有另外新增結束 API 或關鍵字判斷。
- 模型回傳 ready 表示探究進度已具備條件；這個最小串接版本沒有另做同意結束的流程，因此仍可繼續到回合上限或學生明確要求停止。
- 完成後只顯示本次結束與返回問題列表，不生成報告、不觸發全班統整。

## 如何沿用 AI，而不用八欄設定頁

原型 Stage 2 的提示詞需要一份內部對話背景物件。本版轉接器在 service.ts 的 briefFromTopic 直接把 PR205 已有的標題、描述、年齡、回合數轉成原型所需格式；探究方向採固定、中立的預設，開場白直接由題目產生。它是對話提示詞的內部輸入，不是新增的教師設定流程。

因此本版不包含 Stage 1 產生題目設定邏輯、設定表單、設定 API、設定版本或發布檢查。學生可以選題後直接聊天。

保留的原型邏輯：

- Stage 2 有效性提示詞與對話提示詞原文。
- 原型的進度欄位、回覆 schema 與 normalizeProgress。
- 先判斷 validity，YES 才產生正式回覆。

必要的轉接差異：

- 原型中與網頁／Cloudflare 綁定的讀取金鑰方式，改為 Node.js 伺服器環境變數。
- 有效性判斷原本寫死的模型，改與對話共用 OPENROUTER_MODEL，避免測試機上指定模型不可用。
- 為即時回覆加入供應商 SSE 傳輸與 studentMessage 提取；完整 JSON 仍須通過原型結構驗證。
- 不攜入 Stage 1、個人報告、全班統整或 prototype 前端。

## 這一階段的界線

只有聊天真正走獨立 AI API。main 的帳號、課程權限、資料庫、課程列表完成狀態、個人報告與全班分類都未整合；main 後端原始碼完整保留。
API 的對話存在記憶體中；瀏覽器分頁保存的是 Session 識別與存取憑證，不保存 OpenRouter 金鑰。服務重啟後重新進入題目會建立新 Session。
原 PR205 Debug 的「全班完成」「重設資料」等操作僅影響原有示範資料，不會改動本服務的真實對話。
