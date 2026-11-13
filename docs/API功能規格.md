# API 功能規格

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
- 成功回應: `course_id`, `name`, `description`, `teacher_name`, `my_role`, `my_permissions`, `invite_code`, `default_model`{id, name}
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
- 授權: 已登入
- 輸入資料: `invite_code`
- 成功回應: `course_id`, `name`, `invite_code`, `my_role`, `message`
- 錯誤:
    - 邀請碼格式無效 (422)
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
助教權限有四項，如下表說明

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
- 功能說明: 老師輸入已註冊帳號，指派為本課程助教並勾選權限。原為本課程學生者改任助教時保留歷史對話，並從學生統計排除
- 呼叫方式: POST /courses/{courseId}/tas
- 授權: 老師
- 輸入資料: `account_id`, `permissions`(僅接受 edit_topics, view_reports, edit_summary, view_members)
- 成功回應: `user_id`, `account_id`, `name`, `permissions`, `message`
- 錯誤:
    - 帳號未填寫或含未知權限 (422)
    - 非該課程老師 (403)
    - 查無此帳號 (404)
    - 已是本課程助教，或帳號身分不允許（如本課程老師、管理員）(400)

### 更新助教權限
- 功能說明: 老師逐項更新助教權限；儲存後下一次 API 請求立即依新權限檢查
- 呼叫方式: PUT /courses/{courseId}/tas/{userId}
- 授權: 老師
- 輸入資料: `permissions`
- 成功回應: `user_id`, `permissions`, `message`
- 錯誤:
    - 含未知權限 (422)
    - 非該課程老師，或助教嘗試修改自己的權限 (403)
    - 查無此助教 (404)

### 撤銷助教
- 功能說明: 老師撤銷助教的教學存取；原為學生者依核定政策恢復學生資格，並保存角色變更紀錄
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

- 「設定權限」指：老師、助教需 `edit_topics`
- AI 長工作的傳輸方式（同步、輪詢或 SSE）待前後端共同確認，不得因前端請求逾時造成無提示中斷

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
- 成功回應: `course_id`, `name`, `invite_code`, `my_role`, `my_permissions`, `topics`[`topic_id`, `title`, `description`, `topic_status`（`setup` / `conversation` / `summary`）, `age_band`, `max_turns`, 依身分另含下列欄位]
    - 學生: 只列 `conversation`、`summary` 階段的題目；另含 `session_status`（未進入時為 null）, `session_id`
    - 老師與助教: `answered_count`, `student_count`
- 錯誤:
    - 非課程成員或查無此課程 (404)

### 建立題目
- 功能說明: 在課程中建立新題目，只填標題；建立後 `topic_status` 為 `setup`，再進入題目完成設定
- 呼叫方式: POST /courses/{courseId}/topics
- 授權: 老師、助教需 `edit_topics`
- 輸入資料: `title`（作為八欄 `topic` 的初始值）
- 成功回應: `topic_id`, `course_id`, `title`, `topic_status`（`setup`）, `version`, `message`
- 錯誤:
    - 標題未填寫 (422)
    - 無權限 (403)
    - 查無此課程 (404)

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

### 取得題目設定
- 功能說明: 開啟題目設定頁（`setup` 階段可編輯，之後唯讀）；尚未設定的欄位為 null
- 呼叫方式: GET /topics/{topicId}/setup
- 授權: 設定權限
- 輸入資料: 無
- 成功回應: `topic_id`, `course_id`, `version`, `topic_status`, `content_language`, `model_id`, `setup`（八欄設定物件，欄位見上表）
- 錯誤:
    - 無權限 (403)
    - 查無此題目 (404)

### AI 產生題目設定
- 功能說明: 將老師輸入的設定（年齡層、回合上限、內容語言、課程描述）交由 AI 整理成八欄建議，並產生釐清題（同一題目累計最多三題）；不寫入題目，需另呼叫儲存題目設定
- 呼叫方式: POST /topics/{topicId}/setup/generate
- 授權: 設定權限
- 輸入資料: `age_band`, `max_turns`, `content_language`, `course_description`, `model_id`
- 成功回應: 同「取得題目設定」
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目已不在設定階段 (400)
    - AI 服務失敗 (502／503)

### AI 依回饋修訂題目設定
- 功能說明: 以目前設定（含手動修改）與老師回饋重新產生八欄；不寫入題目，需另呼叫儲存題目設定
- 呼叫方式: POST /topics/{topicId}/setup/refine
- 授權: 設定權限
- 輸入資料: `setup`（含手動修改）, `feedback`
- 成功回應: 同「取得題目設定」
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目已不在設定階段 (400)

### 儲存題目設定
- 功能說明: 儲存 `setup` 階段的題目設定，以 `expected_version` 檢查並發衝突
- 呼叫方式: PUT /topics/{topicId}/setup
- 授權: 設定權限
- 輸入資料: `expected_version`, `content_language`, `model_id`, `setup`
- 成功回應:「取得題目設定」的回應, `message`
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此題目 (404)
    - 版本不符，需重新取得最新設定後再送出 (400)
    - 題目已不在設定階段 (400)

### 發布題目
- 功能說明: 老師在交易內將題目從 `setup` 原子性轉為 `conversation`，固定八欄、內容語言與模型，開放學生對話；發布前前端須顯示確認
- 呼叫方式: POST /topics/{topicId}/publish
- 授權: 老師
- 輸入資料: `expected_version`
- 成功回應:「取得題目設定」的回應, `message`
- 錯誤:
    - 非該課程老師 (403)
    - 查無此題目 (404)
    - 版本不符，或設定未完整，需補齊或重新取得後再送出 (400)
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
- 功能說明: 學生第一次進入題目時建立本人 Session，固定題目設定、內容語言、模型及設定版本。已有 Session 時（題目列表的 `session_id` 不為 null）前端應改用 `GET /sessions/{sessionId}/messages`
- 呼叫方式: POST /topics/{topicId}/sessions
- 授權: 學生
- 輸入資料: 無
- 成功回應: `session_id`, `topic_id`, `session_status`
- 錯誤:
    - 非課程學生 (403)
    - 查無此題目，或題目仍在 `setup` (404)
    - 題目已進入 `summary`，不能再開始對話；或本人已有此題目的 Session (400)

### 取得對話紀錄
- 功能說明: 取得本人 Session 的正式訊息歷史與進度，也用於斷線後校準
- 呼叫方式: GET /sessions/{sessionId}/messages
- 授權: 本人
- 輸入資料: 無
- 成功回應: `messages`[`message_id`, `sender`（`ai` / `student`）, `content`, `created_at`], `session_status`, `max_turns`, `completed_turns`, `goal_reached`, `awaiting_end_consent`
- 錯誤:
    - 非此對話擁有者 (403)
    - 查無此對話 (404)

### 發送回答並串流接收 AI 回覆 (SSE)
- 功能說明: 學生送出回答，以 `text/event-stream` 接收 AI 回覆。同一筆重試沿用相同 `request_id`，後端不得重複儲存、扣回合或計費
- 呼叫方式: POST /sessions/{sessionId}/messages/stream
- 授權: 本人
- 輸入資料: `content`（最多 6000 字元，不可空白）, `request_id`
- 成功回應: 串流事件
    - `data` 事件: 可直接接續的文字片段
    - `done` 事件: `message_id`, `completed_turns`, `is_completed`, `awaiting_end_consent`
- 錯誤:
    - 訊息內容為空或超過上限 (422)
    - 非此對話擁有者 (403)
    - 查無此對話 (404)
    - 對話已完成、已達回合上限，或題目已進入 `summary` (400)
    - 同一 Session 有其他請求進行中，待其完成後再送出 (400)
    - AI 服務失敗 (502／503)

### 結束或繼續對話
- 功能說明: 達成探究目標時學生同意結束或選擇繼續；或退出探究（標記 ABANDONED，不列完成、不產生報告）
- 呼叫方式: POST /sessions/{sessionId}/end
- 授權: 本人
- 輸入資料: `action`（`complete` / `continue` / `abandon`）
- 成功回應: `session_id`, `session_status`, `message`
- 錯誤:
    - 動作值無效 (422)
    - 非此對話擁有者 (403)
    - 查無此對話 (404)
    - 對話已結束（已完成或已退出），無法再變更 (400)
    - 尚未達成探究目標就要求 `complete`，可繼續對話後再送出 (400)

### 取得本人個人報告
- 功能說明: 對話完成後取得本人結構化報告；報告準備中時回傳處理狀態供前端輪詢
- 呼叫方式: GET /sessions/{sessionId}/report
- 授權: 本人
- 輸入資料: 無
- 成功回應: `report_status`（`pending` / `processing` / `ready` / `failed`）, `report`（`ready` 時才有值）包含
    - 識別及完成資訊: `report_id`, `version`, `session_id`, `topic_id`, `anonymous_id`, `completed_at`, `completed_turns`, `completion_reason`
    - `viewpoint_summary`, `final_viewpoint`, `viewpoint_status`
    - `reasons`, `strongest_reason`, `challenges`[`challenge`, `responded`], `revision_or_defense`, `focus_connection`, `other_perspectives`, `open_questions`
    - `evidence_status`（`sufficient` / `partial` / `insufficient`）, `limitations`
    - `timeline`[`turn`, `question`, `evidence`, `viewpoint_before`, `viewpoint_after`, `change_type`, `attribution`（`explicit` / `sequence_only` / `none`）]
    - 證據引用格式: `message_id`, `turn`, `quote`
    - 不包含學生姓名
- 錯誤:
    - 非此對話擁有者 (403)
    - 查無此對話 (404)
    - 對話尚未完成 (400)

---

## 全班報告與摘要

### 取得教學端學生報告
- 功能說明: 教學端查看題目的各項人數與學生報告，每份報告附學生註冊姓名
- 呼叫方式: GET /topics/{topicId}/reports
- 授權: 老師、助教需 `view_reports`
- 輸入資料: 無
- 成功回應: `class_size`, `completed_count`, `ready_count`, `processing_count`, `failed_count`, `summary_version`（分群標籤所依據的摘要版本，即「取得教學端摘要」的最新版本；尚無摘要時為 null）, 
    - `groups`[`group_id`, `name`, `count`]該版本的群組清單，供前端產生篩選 tag；尚無摘要時為空陣列
    - `reports`[個人報告的 `report` 結構, `student_display_name`, `group_ids`(此學生在哪一 group)]
    - 前端依 `group_ids` 做 tag 篩選，`group_ids` 為空且 `summary_version` 不為 null 者即為「未分類」
- 錯誤:
    - 無權限 (403)
    - 查無此題目 (404)

### 取得教學端摘要
- 功能說明: 讀取最新版本的摘要（含學生是否已看到哪個版本）
- 呼叫方式: GET /topics/{topicId}/summary
- 授權: 老師、助教需 `edit_summary` 或 `view_reports`
- 輸入資料: 無
- 成功回應: `topic_status`, `published_version`（學生目前看到的版本號，沒有則 null）, `summary`（最新版本，題目尚未進入 `summary` 時為 null），結構為
    - `summary_id`, `version`, `summary_status`（`draft` / `reviewed` / `published` / `withdrawn`）, `overview`, `viewpoint_summary`, `denominator`, `created_at`, `updated_at`（最後一次產生或修訂時間）
    - `groups`[`group_id`, `name`, `conditions`, `count`, `percentage`, `report_ids`]
    - `ungrouped_report_ids`
- 錯誤:
    - 無權限 (403)
    - 查無此題目 (404)

### 產生摘要草稿
- 功能說明: 以 `ready` 報告動態分群產生新摘要草稿，不自動發布，不影響學生已看到的版本。題目在 `conversation` 時第一次呼叫，會把 `topic_status` 轉為 `summary` 並結束學生對話（不可退回）
- 呼叫方式: POST /topics/{topicId}/summary
- 授權:
    - 題目在 `conversation`（會結束學生對話）: 僅老師
    - 題目已在 `summary`（重新產生）: 老師、助教需 `edit_summary`
- 輸入資料: 無
- 成功回應: `topic_status`（`summary`）, `published_version`, `summary`（結構同上，`summary_status` 為 `draft`）
- 錯誤:
    - 無權限 (403)
    - 查無此題目 (404)
    - 題目仍在 `setup`，或沒有可用報告 (400)
    - AI 服務失敗 (502／503)

### 修訂摘要草稿
- 功能說明: 修訂草稿文字；修訂後撤銷審閱狀態，回到 `draft`
- 呼叫方式: PATCH /topics/{topicId}/summary
- 授權: 老師、助教需 `edit_summary`
- 輸入資料: `version`, `overview`, `viewpoint_summary`
- 成功回應: `summary`（結構同上，`summary_status` 為 `draft`）
- 錯誤:
    - 欄位不符規則 (422)
    - 無權限 (403)
    - 查無此摘要 (404)
    - 版本不符 (400)

### 標記摘要審閱完成
- 功能說明: 老師確認統計範圍與表述後標記 `reviewed`
- 呼叫方式: POST /topics/{topicId}/summary/review
- 授權: 老師
- 輸入資料: `version`
- 成功回應: `version`, `summary_status`（`reviewed`）, `message`
- 錯誤:
    - 非該課程老師 (403)
    - 查無此摘要 (404)
    - 版本不符 (400)

### 發布摘要
- 功能說明: 老師將同一個 `reviewed` 版本發布給學生，成為不可變的發布快照
- 呼叫方式: POST /topics/{topicId}/summary/publish
- 授權: 老師
- 輸入資料: `version`
- 成功回應: `version`, `summary_status`（`published`）, `message`
- 錯誤:
    - 非該課程老師 (403)
    - 查無此摘要 (404)
    - 版本不符或尚未審閱 (400)

### 撤回摘要
- 功能說明: 老師撤回目前發布版本，學生端不再取得該摘要
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
- 功能說明: 取得本人本月 AI 用量
- 呼叫方式: GET /users/me/ai/usage
- 輸入資料: 無
- 成功回應: `month`, `total_tokens`, `input_tokens`, `output_tokens`, `request_count`, `by_stage`（分階段統計）, `cost_usd`（無資料時為 null，不代表 0）, `cost_source`, `updated_at`
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
