# API 功能規格

> 本文件依 PR #272（實作 cf2c335，含相依 PR）校準，尚不代表 main 或後端已部署。預覽、main 文件及 OpenAPI 產生方式見 [契約版本說明](AI_BACKEND_CONTRACT.md)。


version: 0.2

## 全域規範

- Base URL: `/api/v1`
- 認證機制: Bearer Token (JWT), Request Header: `Authorization: Bearer <access_token>`；登入時 access token 由回應的 `Authorization` 標頭提供

---

## 使用者身份

### 使用者註冊
- 功能說明: 新使用者建立帳號（全域角色為 USER）
- 呼叫方式: POST /auth/register
- 授權: 不需登入
- 輸入資料: `account_id`, `name`, `password`
- 成功回應: `account_id`, `name`, `role`, `message`
- 錯誤:
    - 欄位未填寫或格式不符 (422)
    - 帳號已存在或為保留帳號名稱 (400)

### 使用者登入
- 功能說明: 帳號密碼驗證並取得登入憑證
- 呼叫方式: POST /auth/login
- 授權: 不需登入
- 輸入資料: `account_id`, `password`
- 成功回應: 回應標頭 `Authorization` 帶 access token
    body: `account_id`, `name`, `role`（陣列，可以包含以下身份："USER" or "SUPERADMIN" or "TEACHER"）, `preferred_language`, `must_change_password`
- 錯誤:
    - 帳號或密碼未輸入 (422)
    - 帳號或密碼錯誤 (401)
    - 帳號已停用 (403)

### 使用者登出
- 功能說明: 登出並清除登入狀態
- 呼叫方式: POST /auth/logout
- 授權: 已登入
- 輸入資料: 無
- 成功回應: `ok`（true）

### 取得當前使用者資訊
- 功能說明: 重新確認目前帳號（頁面重整、Header 顯示及首頁導向）
- 呼叫方式: GET /users/me
- 授權: 已登入
- 輸入資料: 無
- 成功回應: `account_id`, `name`, `role`, `preferred_language`, `must_change_password`

### 修改密碼
- 功能說明: 使用者修改密碼
- 呼叫方式: PUT /auth/password
- 授權: 已登入
- 輸入資料: `old_password`, `new_password`
- 成功回應: `message`
- 錯誤:
    - 新密碼格式不符 (422)
    - 原密碼輸入錯誤 (400)

### 更新使用者偏好
- 功能說明: 更新使用者介面偏好語言
- 呼叫方式: PATCH /users/me/preferences
- 授權: 已登入
- 輸入資料: `preferred_language`（僅接受 `zh-TW` / `en` / `es`）
- 成功回應: `preferred_language`, `message`
- 錯誤:
    - 未登入或憑證過期 (401)
    - 語言代碼無效 (400)
    - 欄位缺漏或格式不符 (422)

---

## 課程 Course

### 取得我的課程列表
- 功能說明: 取得使用者擔任老師、助教或學生的所有課程，不依身分拆成不同列表
- 呼叫方式: GET /courses
- 授權: 已登入
- 輸入資料: 無
- 成功回應: 課程清單 [`course_id`, `name`, `description`, `teacher_name`, `topic_count`, `my_role`(`teacher` / `ta` / `student`),`my_permissions`(本人在此課程的助教權限陣列，見「課程名單」的權限表；僅助教有值，其餘 role 為空陣列), `invite_code`, `student_count`(僅 `teacher`、具 `view_members` 的 TA)]

### 取得課程資訊
- 功能說明: 進入課程頁面時取得課程基本資訊及本人在此課程的身分
- 呼叫方式: GET /courses/{courseId}
- 授權: 老師、助教、學生
- 輸入資料: 無
- 成功回應: `course_id`, `name`, `description`, `teacher_name`, `my_role`, `my_permissions`, `invite_code`
- 錯誤:
    - 非課程成員或查無此課程 (404)

### 建立課程
- 功能說明: 老師建立新課程，系統自動產生課程邀請碼
- 呼叫方式: POST /courses
- 授權: 全域角色為 TEACHER
- 輸入資料: `name`（必填）, `description`（選填）
- 成功回應: `course_id`, `name`, `description`, `invite_code`, `my_role`, `message`
- 錯誤:
    - 課程名稱未填寫 (422)
    - 非老師身分 (403)

### 更新課程
- 功能說明: 老師修改課程名稱及描述
- 呼叫方式: PUT /courses/{courseId}
- 授權: 老師
- 輸入資料: `name`, `description`
- 成功回應: `course_id`, `name`, `description`, `invite_code`, `message`
- 錯誤:
    - 課程名稱未填寫 (422)
    - 非該課程老師 (403)
    - 查無此課程 (404)

### 刪除課程
- 功能說明: 老師刪除整門課程，交易式連帶刪除題目、成員、對話、報告與摘要，不可回復
- 呼叫方式: DELETE /courses/{courseId}
- 授權: 老師
- 輸入資料: 無
- 成功回應: HTTP 204；課程已不存在時同樣 204（冪等）
- 錯誤:
    - 非該課程老師 (403)

### 透過邀請碼加入課程
- 功能說明: 使用者輸入老師提供的課程邀請碼，以學生身分加入課程
- 呼叫方式: POST /courses/join
- 授權: 全域角色為 USER（老師帳號不可加入）
- 輸入資料: `invite_code`
- 成功回應: `course_id`, `name`, `invite_code`, `my_role`, `message`
- 錯誤:
    - 邀請碼格式無效 (422)
    - 非學生帳號 (403)
    - 查無此邀請碼對應的課程 (404)
    - 已經是該課程學生 (400)
    - 已是該課程的老師或助教 (400)

### 學生退出課程
- 功能說明: 學生撤銷本人在該課程的存取，不刪除整門課程
- 呼叫方式: DELETE /courses/{courseId}/member
- 授權: 學生
- 輸入資料: 無
- 成功回應: HTTP 204；已不在課程中時同樣 204
- 錯誤:
    - 老師或助教不可透過此 API 退出 (403)

---

## 課程名單
助教權限有四項，如下表說明。指派助教時可省略 `permissions`，省略即給予全部四項；其他 API 照常回傳 `permissions` / `my_permissions`，前端不需要時可忽略

| permission | 允許做的事 |
| --- | --- |
| `edit_topics` | 可建立題目、修改 `setup` 階段題目的設定（AI 產生、修訂、儲存） |
| `view_reports` | 檢視學生個人報告、觀點 tag，以及摘要分組與報告中的學生姓名 |
| `edit_summary` | 在 `summary` 階段重新產生及修訂摘要草稿；不能審閱、發布或撤回 |
| `view_members` | 檢視學生名單；不能移除學生或管理助教 |

### 取得課程成員名單
- 功能說明: 取得課程的學生及／或助教名單，以 `role` 參數區分
- 呼叫方式: GET /courses/{courseId}/members?role={role}
- 授權:
    - `role=student`: 老師、助教需 `view_members`
    - `role=ta` 或未帶 `role`: 老師
- 輸入資料: `role`（query 參數，選填）
    - `student`: 只回傳學生
    - `ta`: 只回傳助教
    - 未帶: 學生與助教一起回傳
- 成功回應: 成員清單[`user_id`, `account_id`, `name`, `role`(`student` / `ta`), `joined_at`, `permissions`(僅 `ta` 有值，學生為空陣列)]
- 錯誤:
    - `role` 值無效 (422)
    - 無權限 (403)
    - 查無此課程 (404)

### 移除學生
- 功能說明: 老師將學生從課程中移除，撤銷其課程資格；歷史資料保留政策依待決事項
- 呼叫方式: DELETE /courses/{courseId}/students/{userId}
- 授權: 老師
- 輸入資料: 無
- 成功回應: HTTP 204；學生已不在課程中時同樣 204
- 錯誤:
    - 非該課程老師 (403)
    - 查無此課程 (404)

### 指派助教
- 功能說明: 老師輸入學生帳號（全域角色為 USER），指派為本課程助教並給予權限（未指定時給予全部四項）；老師帳號與管理員不可擔任助教。原為本課程學生者改任助教時保留歷史對話，並從學生統計排除；不在本課程者直接以助教身分加入課程。確認彈窗先以 `check: true` 呼叫，只做檢查並取得姓名、不寫入，讓錯誤在按下「新增」前就能顯示；確認後再以 `check: false`（或不帶）正式指派
- 呼叫方式: POST /courses/{courseId}/tas
- 授權: 老師
- 輸入資料: `account_id`, `permissions`（選填，僅接受 edit_topics, view_reports, edit_summary, view_members；省略時給予全部四項）, `check`（選填，只接受 `true` / `false`，預設 `false`）
- 成功回應: `user_id`, `account_id`, `name`, `permissions`, `message`（`check: true` 時為 `TA can be assigned`，正式指派為 `TA assigned`）
- 錯誤:
    - 帳號未填寫、含未知權限，或 `check` 不是 `true` / `false` (422)
    - 非該課程老師 (403)
    - 查無此帳號 (404)
    - 指派對象已是本課程助教，或帳號不是學生帳號（全域角色為 TEACHER，或為管理員），或同時有其他請求變更了該帳號的課程身分 (400)

### 更新助教權限
- 功能說明: 老師逐項更新助教權限；儲存後下一次 API 請求立即依新權限檢查。助教已不分權限，前端不使用此 API，暫時保留
- 呼叫方式: PUT /courses/{courseId}/tas/{userId}
- 授權: 老師
- 輸入資料: `permissions`
- 成功回應: `user_id`, `permissions`, `message`
- 錯誤:
    - 含未知權限 (422)
    - 非該課程老師，或助教嘗試修改自己的權限 (403)
    - 查無此助教 (404)

### 撤銷助教
- 功能說明: 老師撤銷助教，並直接將其移出課程；助教權限與其在本課程的歷史對話一併刪除，與移除學生相同。
- 呼叫方式: DELETE /courses/{courseId}/tas/{userId}
- 授權: 老師
- 輸入資料: 無
- 成功回應: HTTP 204
- 錯誤:
    - 非該課程老師 (403)
    - 查無此助教 (404)

---

## 題目 TOPIC

### 題目八欄設定

| 欄位 | 欄位代碼 | 規則 |
| --- | --- | --- |
| 學習者年齡層 | `age_band` | 只接受 `13-15`、`16-18`、`university_plus` |
| 對話回合上限 | `max_turns` | 只接受整數 5、10、15 |
| 主題 | `topic` | 不得空白 |
| 核心探究問題 | `core_question` | 不得空白 |
| 探究重點 | `inquiry_focus` | 不得預先指定學生必須接受的結論 |
| 必要背景資訊 | `background_info` | 不把未查證資訊寫成事實 |
| 排除事項 | `exclusions` | 無限制時填「未指定」 |
| 開場訊息 | `opening_message` | AI 產生，可在設定階段單獨重產；可為空（AI 失敗時題目仍可建立與儲存） |

### 題目階段 `topic_status`

題目只有一個狀態欄位 `topic_status`，三個階段單向前進、不可退回；題目可在任何階段刪除。

| `topic_status` | 階段 | 進入方式 | 規則 |
| --- | --- | --- | --- |
| `setup` | 題目設定 | 建立題目 | 設定 API 可用；學生看不到此題目 |
| `conversation` | 學生對話 | 老師發布題目 | 鎖定八欄、內容語言與模型；學生可建立／繼續 Session |
| `summary` | 觀點摘要 | 老師第一次產生摘要草稿 | 學生不能再建立 Session 或送出訊息；未完成的 Session 保留但不計入完成數；摘要內的細分狀態見 `summary_status` |

- 「設定權限」指：老師、助教需 `edit_topics` 權限

### 取得可用模型清單
- 功能說明: 取得供應商目錄中的可用模型及單價
- 呼叫方式: GET /inquiry-models
- 授權: 全域角色為 TEACHER，或任一課程的助教
- 輸入資料: 無
- 成功回應: 模型清單[`model_id`, `name`, `description`, `provider_id`, `input_price_usd`, `output_price_usd`（每百萬 token）]

### 取得課程題目列表
- 功能說明: 課程頁面取得題目列表；同一端點依身分過濾資料範圍
- 呼叫方式: GET /courses/{courseId}/topics
- 授權: 老師、助教、學生
- 輸入資料: 無
- 成功回應: `course_id`, `name`, `invite_code`, `my_role`, `my_permissions`, `topics`[`topic_id`, `title`, `description`, `topic_status`（內容見上方表格）, `age_band`, `max_turns`, 依身分另含下列欄位]
    - 學生: 只列 `conversation`、`summary` 階段的題目；另含 `session_status`（此列表為 `IN_PROGRESS` / `COMPLETED`，未進入時為 null；不同於 Session API 的小寫 outcome）, `session_id`
    - 老師與助教: `answered_count`, `student_count`
- 錯誤:
    - 非課程成員或查無此課程 (404)

### 建立題目
- 功能說明: 「新增活動」頁送出後，後端以選定模型將課程描述交由 AI 產生八欄設定並建立題目，將 `topic_status` 設為 `setup`
- 呼叫方式: POST /courses/{courseId}/topics
- 授權: 老師、助教需 `edit_topics`
- 輸入資料: `age_band`, `max_turns`, `course_description`（不可空白，最多 6000 字元）
- 成功回應: 同「取得題目設定」
- 錯誤:
    - 欄位未填寫或不符規則、模型代號無效 (422)
    - 無權限 (403)
    - 查無此課程 (404)
    - AI 服務失敗 (502／503)

### 刪除題目
- 功能說明: 老師刪除題目，連帶刪除對話、報告與摘要，沒有封存
- 呼叫方式: DELETE /topics/{topicId}
- 授權: 老師
- 輸入資料: 無
- 成功回應: HTTP 204
- 錯誤:
    - 非該課程老師 (403)
    - 查無此題目 (404)

---

## 題目設定階段

目前候選版本的實際 API、SSE、錯誤碼與時序圖見 [AI backend contract](AI_BACKEND_CONTRACT.md)。以下標註「尚未實作」的欄位或權限不是可用功能；後續修正不得只修改文件來掩蓋程式缺口。

### 取得題目設定
- 功能說明: 開啟題目設定頁（`setup` 階段可編輯，之後唯讀），null 值的欄位會省略（包含 setup 內的欄位），前端須接受缺少可選 key
- 呼叫方式: GET /topics/{topicId}/setup
- 授權: 設定權限（目前程式仍要求全域老師及課程老師；助教支援待 BE-01 修正）
- 輸入資料: 無
- 成功回應: `topic_id`, `course_id`, `topic_status`, `model_id`, `content_language`, `setup`{八欄設定物件，欄位見上表}
- 錯誤:
    - 無權限 (403)
    - 查無此題目 (404)

### AI 產生題目設定建議
- 呼叫方式: POST /topics/{topicId}/setup/generate
- 授權: 目前仍限老師及課程老師檢查；助教設定權限缺口另追蹤
- 輸入資料: `age_band`, `max_turns`, `content_language`, `course_description`, `model_id`
- 成功回應: `topic_id`, `course_id`, `topic_status`, `model_id`, `content_language`, `setup`，以及 `assessments`, `clarification_questions`, `suggestions`, `warnings`
- 僅回傳建議，不儲存設定、語言或模型；採用建議時，PUT setup 或 POST publish 須明確傳入 model_id／content_language；省略時保留原值
- 錯誤: 非 setup (400)、未授權 (401／403)、題目不存在 (404)、輸入或模型目錄不合法／語意需修訂 (422)、模型失敗 (502／503)、模型逾時 (504)
- `422.detail` 可能是請求驗證陣列，也可能是模型建議修訂的字串

### AI 依回饋修訂題目設定
- 功能說明: 「確認活動設定」頁的「重新產生」按鈕按下後呼叫，依老師回饋重新產生八欄設定及回饋；只回傳建議，不自動儲存
- 呼叫方式: POST /topics/{topicId}/setup/refine
- 授權: 設定權限（目前程式仍要求全域老師及課程老師；助教支援待 BE-01 修正）
- 輸入資料: `setup`, `feedback`
- 成功回應: 同「取得題目設定」
- 錯誤:
    - 欄位不符規則，或模型要求修訂描述 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目已不在設定階段 (400)
    - AI 服務失敗 (502／503)
    - 模型逾時 (504)

### AI 重新產生開場訊息
- 功能說明: 「確認活動設定」頁開場訊息欄的「重新產生」按鈕按下後呼叫，依目前設定（含手動修改）重新產生並儲存 `opening_message` 與 revision；不一併儲存其他畫面欄位
- 呼叫方式: POST /topics/{topicId}/setup/opening-message
- 授權: 設定權限（目前程式仍要求全域老師及課程老師；助教支援待 BE-01 修正）
- 輸入資料: `setup`
- 成功回應: `opening_message`
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目已不在設定階段 (400)
    - AI 服務失敗 (502／503)
    - 模型逾時 (504)
    - 生成期間設定被其他請求修改 (409)

### 儲存題目設定
- 功能說明: 「確認活動設定」頁的「儲存草稿」按鈕按下後呼叫，儲存 `setup` 階段的八欄設定
- 呼叫方式: PUT /topics/{topicId}/setup
- 授權: 設定權限（目前程式仍要求全域老師及課程老師；助教支援待 BE-01 修正）
- 輸入資料: `setup`
- 成功回應:「取得題目設定」的回應, `message`
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目已不在設定階段 (400)

### 發布題目
- 功能說明: 先把畫面上的八欄存下來，設定完整才在同一筆交易把題目從 `setup` 轉為 `conversation`，固定八欄、內容語言與模型，開放學生對話；發布前前端須顯示確認。不完整的內容不會留下
- 呼叫方式: POST /topics/{topicId}/publish
- 授權: 老師
- 輸入資料: `setup`（八欄），選填 `model_id`、`content_language`；省略保留原值，null／空白不合法，模型須存在於目錄。
- 成功回應:「取得題目設定」的回應, `message`
- 錯誤:
    - 欄位不符規則，或設定未完整 (422)
    - 非該課程老師 (403)
    - 查無此題目 (404)
    - 題目已不在設定階段 (400)

---

## 題目對話階段

### 取得題目背景說明
- 功能說明: 對話側欄顯示探究背景
- 呼叫方式: GET /topics/{topicId}/explanation
- 授權: 老師、助教、學生（學生限 `conversation`、`summary` 階段）
- 輸入資料: 無
- 成功回應: `topic_id`, `title`, `background`, `key_terms`
- 錯誤:
    - 非課程成員或查無此題目 (404)

### 建立對話 Session
- 功能說明: 首次進入時建立本人 Session；已有 Session 時回傳同一筆及其目前 outcome，不會重開已結束的對話。發布後鎖定題目設定，不代表此 API 另存完整設定快照
- 呼叫方式: POST /topics/{topicId}/sessions
- 授權: 已登入且為課程成員（目前並未限定課程學生身分）
- 輸入資料: 無
- 成功回應: `session_id`, `topic_id`, `session_status`（`open` / `completed` / `ended` / `abandoned` / `closed_by_summary`）
- 錯誤:
    - 非課程成員 (403)
    - 查無此題目，或題目仍在 `setup` (404)
    - 題目已進入 `summary`，且本人還沒有 Session (400)
    - 摘要工作仍有有效 pending/processing lease，暫停建立新 Session (409)

### 取得對話紀錄
- 功能說明: 取得本人 Session 的正式訊息歷史與進度，也用於斷線後校準
- 呼叫方式: GET /sessions/{sessionId}/messages
- 授權: 本人
- 輸入資料: 無
- 成功回應: `messages`[`message_id`, `sender`（`ai` / `student`）, `content`, `created_at`], `session_status`, `max_turns`, `completed_turns`, `goal_reached`, `awaiting_end_consent`, `current_progress`, `report_eligible`, `ending_reason`, `can_finish_early`
- 錯誤:
    - 查無此對話或非本人 (404)

### 發送回答並串流接收 AI 回覆 (SSE)
- 功能說明: 學生送出回答，以 `text/event-stream` 接收 AI 回覆。同一筆重試沿用相同 `request_id` 與 content。已提交的回覆會重播，不再呼叫模型或新增回合；失敗／跨 worker 的請求不保證 provider 只計費一次
- 呼叫方式: POST /sessions/{sessionId}/messages/stream
- 授權: 本人
- 輸入資料: `content`（最多 6000 字元，不可空白）, `request_id`
- 成功回應: 串流事件
    - 未命名事件（標準事件類型 `message`）: 整段回覆文字，多個 data 行以 LF 接合；不是每個網路 chunk 一個事件。模型與交易完成後才開始 SSE
    - `done` 事件: `message_id`, `completed_turns`, `is_completed`, `awaiting_end_consent`, `session_status`, `goal_reached`, `report_eligible`, `ending_reason`, `can_finish_early`
- 錯誤:
    - 訊息內容為空或超過上限 (422)
    - 查無此對話或非本人 (404)
    - 對話已完成、已達回合上限，或題目已進入 `summary` (400)
    - 同一 Session 有其他請求進行中，或生成期間狀態已變更 (409)
    - 超過上下文預算 (413)
    - AI 服務失敗或 tokenizer 不支援 (502／503)
    - SSE 開始前的錯誤為 JSON HTTP 回應，先檢查 status/content-type

### 結束或繼續對話
- 功能說明: 達成探究目標時學生同意結束或選擇繼續；或退出探究（outcome 標記 `abandoned`，不列完成、不產生報告）
- 呼叫方式: POST /sessions/{sessionId}/end
- 授權: 本人
- 輸入資料: `action`（`complete` / `continue` / `abandon` / `finish`）
- 成功回應: `session_id`, `session_status`, `message`, `goal_reached`, `report_eligible`, `ending_reason`, `can_finish_early`
- 錯誤:
    - 動作值無效 (422)
    - 查無此對話或非本人 (404)
    - 重複相同結束動作為200；已結束後要求不相容動作為409
    - 尚未達成探究目標就要求 `complete`，或其他回覆仍在進行中 (409)

`continue` 清除 consent 但保留已達成的 goal，不增加回合上限。`complete` 與 `finish` 結束交易時自動建立 pending 報告。`finish` 至少三次學生回答，否則409；不要求 goal_reached。最後允許的回合由後端自動設 outcome=ended、ending_reason=turn_limit，並排程報告，不需前端再呼叫 end。finish 的 reason=student_requested_stop。goal 保留原值；證據不足不阻擋報告。此為 Chunk06 分支契約，需審核、migration、部署後採用。

### 啟動本人個人報告
- 呼叫方式: POST /sessions/{sessionId}/report
- 授權: 本人；outcome 必須為 `completed` 或 `ended`
- 輸入資料: 無
- 成功回應: HTTP 200，`report_status`, `report`
- 無 attempt、最新失敗或 pending/processing lease 過期：新增 attempt 並排程。仍有效的 pending/processing 或 ready：直接沿用，不強制重新生成
- 錯誤: 未授權 (401／403)、查無此對話或非本人 (404)、outcome 非 completed/ended (409)、UUID 驗證錯誤 (422)
- 啟動後以 GET 同一路徑輪詢；GET 本身不啟動生成

### 取得本人個人報告
- 功能說明: 對話完成後取得本人結構化報告；報告準備中時回傳處理狀態供前端輪詢
- 呼叫方式: GET /sessions/{sessionId}/report
- 授權: 本人
- 輸入資料: 無
- 成功回應: `report_status`（`pending` / `processing` / `ready` / `failed`）, `report`（最新可用的 ready 內容，沒有則 null；最新 attempt 失敗／處理中仍可能帶較早的 ready 內容）包含
    - 目前識別及完成資訊: `report_id`, `version`（目前固定 1）, `session_id`, `topic_id`, `completed_turns`, `completion_reason`（goal_reached / student_requested_stop / turn_limit；舊資料可能為 completed）
    - `ended_at` 記錄可產生報告的結束時間，`goal_reached` 保留實際目標達成狀態；`completed_at` 使用伺服器記錄的對話完成時間（舊資料可能省略）；`anonymous_id` 尚待定義匿名代碼範圍，前端不可假設存在
    - `viewpoint_summary`, `final_viewpoint`, `viewpoint_status`
    - `reasons`, `strongest_reason`, `challenges`[`challenge`, `responded`], `revision_or_defense`, `focus_connection`, `other_perspectives`, `open_questions`
    - `evidence_status`（`sufficient` / `partial` / `insufficient`）, `limitations`
    - `timeline`[`turn`, `question`, `evidence`, `viewpoint_before`, `viewpoint_after`, `change_type`, `attribution`（`explicit` / `sequence_only` / `none`）]
    - 新報告保留 timeline.evidence 字串，另提供 evidence_reference {message_id, turn, quote} 並查核學生訊息來源、回合、原文；舊報告維持可讀但未追溯驗證。此時間線是證據索引，不推定立場改變或因果關係。
    - 不包含學生姓名
- 錯誤:
    - 查無此對話或非本人 (404)
    - outcome 非 completed/ended (409)
    - 可產生報告但尚未建立 report attempt (404)


---

### 教師重試個人報告
- 呼叫方式: POST /topics/{topicId}/reports/{sessionId}
- 授權: 目前為全域老師且具課程 instructor 身分
- 無 request body；回應與本人 report 相同
- 沿用有效 pending/processing 與相容的 ready 報告；失敗／過期可重試。教師端另可重建缺少或不符合原生證據、或探究設定已不匹配的 ready 報告，供 Stage3 使用。只有新增 attempt 才取新 progress snapshot
- 錯誤: 未授權／無權限 (401／403)、題目或屬於該題目的 Session 不存在 (404)、outcome 非 completed/ended (409)、UUID 不合法 (422)

## 全班報告與摘要

### 取得教學端學生報告
- 呼叫方式: GET /topics/{topicId}/reports
- 授權: 全域 teacher 且具課程 instructor 身分；目前未開放一般 TA
- 成功回應: `class_size`, `completed_count`, `ended_count`, `ready_count`, `processing_count`, `failed_count`, `reports`[{`report_status`, `report`, `student_display_name`}]
- `completed_count` 僅計成功完成，`ended_count` 另計提前結束／回合上限。個別 report 可為 null，或在最新 attempt 處理中／失敗時保留舊 ready 內容
- 此列表沒有 `summary_version`、`groups` 或每位學生的 `group_ids`；摘要分組在摘要讀取端點取得
- 錯誤: 無權限 (403)、查無題目 (404)

### 取得教學端摘要
- 功能說明: 讀取摘要。沒帶 `version` 時回最新一版；帶了就回那一版。`published_version` 仍是學生目前看到的版本；`preparation_status` 回報最新生成工作狀態（無工作時為 null）
- 呼叫方式: GET /topics/{topicId}/summary
- 授權: 全域 teacher 且具課程 instructor 身分；目前未開放一般 TA
- 輸入資料: query `version`（可省略；有帶時須為大於等於 1 的整數）
- 成功回應: `topic_status`, `published_version`（學生目前看到的版本號，沒有則 null）, `summary`（沒帶 `version` 時為最新一版，題目尚未進入 `summary` 時為 null；有帶時為該版），結構為
    - `summary_id`, `version`, `summary_status`（`draft` / `reviewed` / `published` / `withdrawn`）, `overview`, `viewpoint_summary`, `denominator`
    - `groups`[`group_id`, `name`, `conditions`, `count`, `percentage`, `report_ids`]
    - `ungrouped_report_ids`
- 錯誤:
    - 版本無效 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 指定的版本不存在 (404)

### 產生摘要草稿
- 功能說明: 以 `ready` 報告動態分群產生新摘要草稿，成功時存成新的一版，不自動發布，不影響學生已看到的版本。必須所有現有對話已結束，且每個可產生報告的對話最新報告均為 ready；成功儲存摘要後才把 topic_status 轉為 summary，不再關閉未結束的學生對話
- 呼叫方式: POST /topics/{topicId}/summary
- 授權: 全域 teacher 且具課程 instructor 身分；目前未開放一般 TA
- 輸入資料: 無
- 成功回應: HTTP 200，`topic_status` 保留目前階段、`published_version`、`summary=null`、`preparation_status=pending`。背景生成；以 GET 同一路徑輪詢 pending/processing/ready/failed。ready 才存入 draft 並切換 summary 階段；失敗不撤回既有發布版本
- 錯誤:
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目仍在 `setup`，或沒有可用報告 (400)
    - 仍有 open 對話、最新報告未 ready，或原生證據不相容需重新生成 (409)
    - 超過50份報告、payload 或模型 token 預算 (413)
    - 模型 tokenizer 不支援 (503)
    - 排程後的模型／驗證失敗以 preparation_status=failed 表示，不會回溯改變已回傳的 HTTP 200

### 修訂摘要草稿
- 功能說明: 以畫面上的文字修訂最新一版。文字有變才存成下一版；文字沒變則版本號不變。狀態回到 `draft`，已發布給學生的快照不變
- 呼叫方式: PATCH /topics/{topicId}/summary
- 授權: 全域 teacher 且具課程 instructor 身分；目前未開放一般 TA
- 輸入資料: `overview`, `viewpoint_summary`（不可空白）
- 成功回應: `summary`（結構同上，`summary_status` 為 `draft`）
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此摘要 (404)

### 標記摘要審閱完成
- 功能說明: 以畫面上的文字標記審閱完成。與最新一版不同時，先存成下一版再標 `reviewed`；沒有變動就只改狀態，版本號不變。若已有別的 `reviewed` 版本，那個版本改為 `withdrawn`
- 呼叫方式: POST /topics/{topicId}/summary/review
- 授權: 老師
- 輸入資料: `overview`, `viewpoint_summary`（不可空白）
- 成功回應: `version`（寫入後的版本號）, `summary_status`（`reviewed`）, `message`
- 錯誤:
    - 欄位不符規則 (422)
    - 非該課程老師 (403)
    - 查無此摘要 (404)

### 發布摘要
- 功能說明: 老師發布最新一版，且該版必須是 `reviewed`。不帶版本號，也不接收畫面上的文字。已有較新的未審閱版本時拒絕發布。前一個 `published` 版本改為 `withdrawn`
- 呼叫方式: POST /topics/{topicId}/summary/publish
- 授權: 老師
- 輸入資料: 無
- 成功回應: `version`（實際發布的版本號）, `summary_status`（`published`）, `message`
- 錯誤:
    - 非該課程老師 (403)
    - 查無此摘要 (404)
    - 最新一版尚未審閱，或已有較新的未審閱版本 (400)。`detail` 為 `version`（最新版本號）, `summary_status`（該版狀態）, `message`

### 撤回摘要
- 功能說明: 老師撤回目前發布版本，學生端不再取得該摘要。最新一版只清掉 `published` 與 `published_version`，不改它的狀態；較舊的發布版改為 `withdrawn`
- 呼叫方式: POST /topics/{topicId}/summary/withdraw
- 授權: 老師
- 輸入資料: 無
- 成功回應: `summary_status`（`withdrawn`）, `message`
- 錯誤:
    - 非該課程老師 (403)
    - 查無已發布摘要 (404)

### 取得學生公開摘要
- 功能說明: 學生取得老師已發布的全班摘要；由後端產生安全公開資料
- 呼叫方式: GET /topics/{topicId}/summary/published
- 授權: 老師、助教、學生
- 輸入資料: 無
- 成功回應: `summary`（沒有發布版本時為 null）包含 `overview`, `viewpoint_summary`, `groups`[`name`, `conditions`, `count`, `percentage`], `ungrouped_count`, `ungrouped_percentage`, `denominator`
    - 不包含同學姓名、匿名代碼、原始引言、`session_id`、`message_id`、`report_id` 或分組的 `report_ids`
- 錯誤:
    - 非課程成員或查無此題目 (404)

---

## AI 金鑰與用量
皆在 /users/me/ai 路徑下，僅限 teacher 可用

### 取得 AI 用量

> 實作狀態：本 usage 修正分支提供真實 provider-request ledger 與聚合，需合併及執行 migration `b8e39a1547c2` 才可採用；main 與 PR239 scaffold 不具備此能力。只包含啟用計量後由本系統發出的請求，不回補歷史／外部帳號用量。

- 功能說明: 依 UTC 月份統計本人作為課程 owner 的 AI 請求（含 TA／學生觸發、背景報告、重試及失敗呼叫），來源為 provider 回傳值
- 呼叫方式: GET /users/me/ai/usage
- 輸入資料: 無
- 成功回應: `month`, `total_tokens`, `input_tokens`, `output_tokens`, `request_count`, `by_stage`（分階段統計，格式見下）, `cost_usd`（無資料或任一請求成本未知時為 null；provider 明確回0才表示0）, `cost_source`, `updated_at`
    - `by_stage`: 陣列，固定 4 筆，依 `setup`、`dialogue`、`report`、`summary` 的順序；本月沒有用量的階段也要回傳（數量為 0、`cost_usd` 為 null）
        - `stage`: `setup`（活動設定）、`dialogue`（學生對話）、`report`（個人報告）、`summary`（全班統整）
        - `request_count`: 整數，實際 provider request 嘗試次數；同一學生回合可能有多個呼叫
        - `total_tokens`, `input_tokens`, `output_tokens`: 整數或 null；任一請求缺該項 usage 時，該項總數為 null，不假裝是0
        - `cost_usd`: 該階段本月花費（美元）；無資料時為 null，不代表 0
    - `by_stage` 範例:
        ```json
        [
          { "stage": "setup", "request_count": 18, "total_tokens": 31200, "input_tokens": 21400, "output_tokens": 9800, "cost_usd": 0.02 },
          { "stage": "dialogue", "request_count": 352, "total_tokens": 80150, "input_tokens": 61800, "output_tokens": 18350, "cost_usd": 0.05 },
          { "stage": "report", "request_count": 36, "total_tokens": 13100, "input_tokens": 9800, "output_tokens": 3300, "cost_usd": 0.01 },
          { "stage": "summary", "request_count": 0, "total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": null }
        ]
        ```
- 錯誤:
    - 非老師身分 (403)

### 取得 API key 設定
- 功能說明: 查詢本人 API key 狀態
- 呼叫方式: GET /users/me/ai/settings
- 輸入資料: 無
- 成功回應: `configured`, `masked_key`, `updated_at`, `default_model`{id, name}
- 錯誤:
    - 非老師身分 (403)

### 設定 API key
- 功能說明: 設定本人 API key；回應與日誌不得包含完整 key
- 呼叫方式: PUT /users/me/ai/api-key
- 輸入資料: `api_key`
- 成功回應: `configured`, `masked_key`, `updated_at`
- 錯誤:
    - key 格式不符 (422)
    - 非老師身分 (403)

### 移除 API key
- 功能說明: 移除本系統保存的 key（不等同於向供應商撤銷 key）；既有用量歷史保留
- 呼叫方式: DELETE /users/me/ai/api-key
- 輸入資料: 無
- 成功回應: HTTP 204
- 錯誤:
    - 非老師身分 (403)

### 設定新題目預設模型
- 功能說明: 設定本人新題目的預設模型，不更改已離開 `setup` 的題目及既有 Session
- 呼叫方式: PATCH /users/me/ai/model
- 輸入資料: `model_id`
- 成功回應: `default_model`{id, name}, `message`
- 錯誤:
    - 模型代號無效 (422)
    - 非老師身分 (403)

---

## 管理員

### 取得老師帳號列表
- 功能說明: 取得所有老師帳號名單
- 呼叫方式: GET /admin/teachers
- 輸入資料: 無
- 成功回應: 老師清單[`id`, `account_id`, `name`, `created_at`]
- 錯誤:
    - 非管理員 (403)

### 建立老師帳號
- 功能說明: 管理員新增老師帳號；系統產生一次性初始密碼，並將 `must_change_password` 設為 true
- 呼叫方式: POST /admin/teachers
- 輸入資料: `account_id`, `name`（不含密碼；規則同註冊）
- 成功回應: `account_id`, `name`, `role`, `password`（一次性初始密碼）, `message`
- 錯誤:
    - 帳號或姓名未填寫或格式無效 (422)
    - 非管理員 (403)
    - 帳號已存在或為保留帳號名稱 (400)

### 刪除老師帳號
- 功能說明: 管理員刪除指定老師帳號，連帶刪除其課程（有其他授課老師的課程保留）
- 呼叫方式: DELETE /admin/teachers/{teacherId}
- 輸入資料: 無
- 成功回應: HTTP 204
- 錯誤:
    - 非管理員 (403)
    - 查無此老師帳號 (404)
    - 目標帳號為設定檔超級管理員，不可刪除 (403)

### 重設老師初始密碼
- 功能說明: 管理員重設老師初始密碼，要求下次登入修改。
- 呼叫方式: POST /admin/teachers/{teacherId}/reset-password
- 輸入資料: 無
- 成功回應: `password`（一次性初始密碼）, `message`
- 錯誤:
    - 非管理員 (403)
    - 查無此老師帳號 (404)
    - 目標帳號為設定檔超級管理員，不可重設 (403)

## 模型與語言設定補充（Chunk02）

建立題目可明確傳入 `model_id`、`content_language`。老師或助教建立時，未指定模型則使用課程建立老師的預設模型，再回退到伺服器設定；失效的已儲存模型回應422。此規則不改變金鑰擁有者。PUT setup 與 POST publish 可傳入上述兩個選填欄位；省略保留原值，null／空白無效。設定讀取、儲存、AI產生、修訂、開場白允許該課程老師或有 edit_topics 的助教；發布僅允許該課程老師。

### Chunk06 frontend ending contract

History/end/SSE done add `report_eligible`, `ending_reason`, `can_finish_early`; SSE done also adds `session_status` and `goal_reached`. `ended` is a new outcome. Do not rely only on `is_completed` to navigate to reports. Report adds `ended_at`, `goal_reached`; teaching list adds `ended_count`. `completed_count` remains successful completions.

Inconclusive reports retain the full report structure, with `evidence_status=insufficient`, observations and `limitations`. A useful partial summary is preferred; missing milestones alone are not inconclusive. `report_status=ready` means generation succeeded, not that learning goals were reached. GET polls automatically started reports; POST retries/reuses or starts legacy missing attempts. No report is created merely by closing the browser. Full sequence charts: [AI_BACKEND_CONTRACT.md](AI_BACKEND_CONTRACT.md).


## 課程 AI 模型與憑證路由（Chunk07/08）

各階段優先使用題目已儲存的模型；未設定時使用 `OPENAI_MODEL`，包含 validity、status、planning、context/catch-up、個人報告與班級摘要。Stage1 generate 的明確模型選擇仍只影響該次產生，需 Save/Publish 才儲存。報告來源快照與摘要請求保留非機密模型資訊；重試已捕捉的請求不改用其他模型。

課程擁有者的個人 key 優先，無個人 key 才使用單一伺服器 `OPENAI_API_KEY`；助教／學生觸發不改變付費者。無法解密或個人 key 呼叫失敗不轉用伺服器額度。憑證不寫入報告、來源快照或摘要 JSON。沒有 key rotation，也沒有新增前端欄位或端點。完整順序圖見 [AI backend contract](AI_BACKEND_CONTRACT.md#model-and-credential-routing-combined-chunk0708)。


## Stage3 原生整合與報告就緒條件

個人報告在各自對話完成／提前結束／回合上限後產生，學生不必等全班即可讀取。班級摘要 POST 必須等待所有現有對話結束，且所有 completed/ended 對話的最新報告為 ready；缺漏、pending/processing/failed 或不相容原生證據回409。舊報告可由教師既有重試端點重新產生。abandoned 與歷史 closed_by_summary 不屬於報告分母。

最多50份報告；超出報告數、payload或token預算回413，無報告回400。分類只使用具立場與理由證據的報告；無法分類的報告仍計入分母，使用既有 ungrouped 欄位表示。群組人數與比例由後端計算，不接受模型計數。

產生期間以有效 lease 阻擋新 session（409），既有個人報告仍可讀取。ready 提交前再次確認無開放對話且來源報告未變；失敗保留原已發布版本。保留原有審核、發布、撤回端點與 DTO，原生詳細結果及來源映射只存在私有 JSON。完整流程見 [AI_BACKEND_CONTRACT](AI_BACKEND_CONTRACT.md#native-stage3-class-synthesis)。


## 教師結束 Stage2（PR #272，尚未部署）

- GET `/topics/{topicId}/conversation-status`：教師查詢 `open_dialogue_count`、`stage2_closed`、`confirmation_required`、`preparation_status`。僅計已建立且 open 的對話，不計未進入學生；讀取不觸發工作。
- POST `/topics/{topicId}/end-conversation`：body `{"confirm_open_dialogues": true}`。若未確認且仍有 open 對話，409 detail 回傳 code 與最新數量，沒有結束副作用。
- 確認後原子結束 open 對話：outcome=ended、reason=teacher_ended_stage2，保留 goal。教師不受三次回答下限限制；topic 立即進入 summary，技術失敗也不重新開放。
- HTTP200 表示已關閉且工作已排程，不代表摘要就緒。後端先等待個人報告再自動統整；GET summary 輪詢工作狀態，原有審閱／發布流程不變。重複關閉沿用有效或 ready 工作，失敗／逾時可重試。
- 零回答：個人報告為 ready/insufficient，明示未提交回答；不呼叫模型、不計入全班分母。全班皆無回答時仍有 denominator0 的誠實證據不足草稿。
- 新端點沿用全域 teacher + course instructor 授權。完整 payload、錯誤、競態、恢復與前端流程見 [teacher closure contract](AI_BACKEND_CONTRACT.md#teacher-controlled-stage2-closure-pr-272-not-deployed)。本提案不修改前端；前端需輪詢／重讀現有狀態才能導頁。


## AI 診斷日誌（usage/diagnostics 修正分支）

HTTP 回應新增 `X-Request-ID`，CORS 已 expose，供前端回報502時定位。後端 `ai_event` 串接 HTTP request/call/job ID，記錄 task、model、prompt 版本/hash、輸出上限、provider status、finish_reason、token/reasoning 數、latency、generation/usage ID。可分辨截斷、JSON、schema、證據引用、provider、timeout；不變更現有 AI 回應/API error 行為。

SQL_ECHO 預設 false。AI_TRACE_ENABLED 預設 false；僅 development 啟用時，原始回應（去除憑證與 reasoning 文字）寫入被 Git 忽略的 `.local/ai-traces`，每 worker1MB/3備份輪替。可能含學生文字，僅供授權測試資料及本機除錯，production 不啟用。完整定位步驟見 [AI debugging](AI_BACKEND_CONTRACT.md#ai-call-debugging-usage-and-diagnostics-follow-up)。此修正不調整1000 token上限或修復502本身。

開發者操作步驟（含啟動指令、如何從 browser 取 X-Request-ID、PowerShell/Bash 搜尋、範例解析、trace 檔案與回報清單）見 [developer walkthrough](AI_BACKEND_CONTRACT.md#developer-walkthrough)。


## Stage2 status 截斷修正（PR274 之後的本地 hot fix）

已用 Luna 重現 legacy progress catch-up 的 provider HTTP200/finish_reason=length：1000 completion tokens 後 JSON 字串未結束，backend 映射502。僅將 cap 改3000 的對照呼叫以1017 tokens 完成，schema/證據均通過；測試用 key/account 有可用額度，非402/429。

status prompt 升版 stage2_status-1.0.1，輸出上限1000→3000，同時套用一般回合與舊對話進度補算；原有 context budget 會計入新 reserve。沒有新增 API 欄位、migration、model 替換、放寬驗證或重試。新增 progress_catch_up_started 診斷 marker。詳見 [truncation hot fix](AI_BACKEND_CONTRACT.md#stage2-status-truncation-hot-fix-local-follow-up-above-pr274)。原始 session/log 未提供，不能斷言每個歷史502皆同因。
