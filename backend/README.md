# Squicrates 後端
## 環境建置

1. 請確認本機已安裝以下工具：
    - Docker & Docker Compose
    - uv
    - Makefile

2. 複製環境設定檔：
    在專案根目錄:
    ```bash
    cp backend/.env.example backend/.env
    cp backend/config.yaml.example backend/config.yaml
    ```
    `.env` 放密鑰；`config.yaml` 放非密鑰本機設定（見下方 Super Admin）。
    老師自備的 OpenRouter key 會加密後存進資料庫。`.env` 的 `TEACHER_API_KEY_SECRET` 是解密用的伺服器金鑰，至少 32 字元，可用 `openssl rand -hex 32` 產生。所有課程 AI 工作（含助教／學生觸發與背景報告）使用課程擁有者的 key；沒設時用單一 `OPENAI_API_KEY`。老師 key 解密或呼叫失敗不會改用伺服器額度；本版本沒有 key rotation。換掉 `TEACHER_API_KEY_SECRET` 之後，已存的老師 key 無法解密。

3. 在 repo 根目錄安裝鎖定的 Python 套件並啟用 pre-commit：
    ```bash
    make -C backend setup
    ```
    `make -C backend setup` 會依 `backend/uv.lock` 安裝套件並安裝 Git hook。提交時 Ruff 會修正 backend Python 的 lint 與格式問題，Gitleaks 會掃描整個 repo 的 staged 內容。

## 設定 Super Admin

管理員權限是靠 `backend/config.yaml` 的帳號名單提升，**不是**改資料庫的 `role`。login / `/users/me` 仍可能回 `USER` 或 `TEACHER`；名單內帳號才能打 `/admin/*`。

1. 先用一般流程註冊並確認帳號的 `account_id`（註冊／登入用的帳號字串）。
2. 編輯 `backend/config.yaml`（沒有就從 example 複製）：

    ```yaml
    # Schema: app.core.yaml_config.YamlConfig
    SUPER_ADMIN_ACCOUNTS: [alice]
    ```

    把 `alice` 換成你的 `account_id`。不需要 admin 時設成 `[]`。
3. **重啟** `make -C backend dev`（設定在行程啟動時載入，改檔後不會熱更新）。
4. `config.yaml` 已 gitignore，不要 commit。

格式範本：`backend/config.yaml.example`。

## 開發用假資料（seed）

本機要測已合併的 auth／admin／學生 session API 時，用固定 catalog 灌入帳號與一門示範課（**僅** `APP_ENV=development`）。

前端／帳密／邀請碼／Topic ID 以 [docs/測試資料.md](../docs/測試資料.md) 為準。後端操作：

```bash
make -C backend db-dev          # 若 Postgres 尚未啟動
make -C backend seed            # 灌 DB + 協助把 dev-admin 寫進 config.yaml
make -C backend db-reset        # 互動確認後清空 schema 再 upgrade + seed
make -C backend db-reset CONFIRM=1   # 非互動（腳本用）
```

- 帳號：`dev-student` / `dev-teacher` / `dev-admin`；共用密碼 `password1`
- 邀請碼：`DEVJOIN01`；topic id：`00000000-0000-4000-8000-000000000201`
- `make seed` 可重複執行（已存在的列會跳過）；改 `config.yaml` 後需**重啟** server
- 可選：在 `.env` 設 `SEED_DEV_DATA=true`，`make -C backend dev` 啟動時（migration 後）只灌 DB、**不**寫 `config.yaml`；預設 `false`

### `SEED_PACKS`（可選：只跑部分 seed pack）

Seed 依 **pack** 分段灌資料。平常不設即可；預設會跑完整核心組，等同前端測試資料文件裡的整套 catalog。

| Pack | 灌入內容 |
|------|----------|
| `auth` | 三個固定帳號（`dev-student` / `dev-teacher` / `dev-admin`）與共用密碼 |
| `course_graph` | 示範課程、邀請碼、topic，並把 `dev-student` 加進該課（依賴上面的帳號已存在） |

`SEED_PACKS` 用來**覆寫**這次要跑哪些 pack（逗號分隔、空白會被忽略）。讀取順序與其他設定相同：行程環境變數或 `backend/.env`（經 `settings`）。

- **未設或空字串** → 跑預設 `auth,course_graph`（順序固定：先 `auth` 再 `course_graph`）
- **有設定** → 只跑列出的 pack；未知名稱會報錯並中止
- **`course_graph` 必須同時含 `auth`**（否則拒絕）；若你寫 `course_graph,auth`，執行時仍會依依賴排成 `auth` → `course_graph`

適用時機例如：只想重灌帳號、暫時不要動課程圖。對 `make seed`、`make db-reset`，以及 `SEED_DEV_DATA=true` 的 lifespan 灌 DB 都生效（後者一樣不寫 `config.yaml`）。

```bash
# backend/.env 或匯出到 shell
SEED_PACKS=auth                 # 只灌帳號
# SEED_PACKS=auth,course_graph  # 與預設相同（可省略）
```

## 啟動開發伺服器
1. 啟動 docker 容器，裡面有 PostgreSQL 和 Redis. 
    在專案根目錄執行：
    ```bash
    make -C backend db-dev
    ```

    檢查容器狀態：
    ```bash
    docker compose ps
    ```

    關閉容器
    ```bash
    make -C backend db-dev-down
    ```

2. 啟動 FastAPI：
```bash
make -C backend dev
```
API 文件:
http://localhost:8000/docs 
http://localhost:8000/redoc

確認 PostgreSQL 與 Redis 連線狀態:
http://localhost:8000/api/v1/health

### GitHub Pages 預覽（靜態 OpenAPI）

CI 會把與本機 `/docs` 同款的靜態 Swagger UI 發到 GitHub Pages（需在 repo Settings → Pages 將 Source 設為 **GitHub Actions**，並視情況保護 `github-pages` Environment）。僅在變更 `backend/**` 或此 workflow 時部署（可用 Actions → API Docs Pages → Run workflow 手動重建）：

- Swagger：`https://<owner>.github.io/<repo>/docs/`
- Redocly：`https://<owner>.github.io/<repo>/redoc/`
- 同 repo PR：`https://<owner>.github.io/<repo>/pr-preview/pr-<n>/docs/`（fork PR 不處理）

本機匯出／預覽（檔案預設在 `docs/openapi/`；`openapi-site` 預覽 URL 仍是 `/docs/`）：

```bash
make -C backend openapi-export               # → docs/openapi/openapi.json
make -C backend openapi-site                 # 建站並在 :8080 起 server → /docs/
make -C backend openapi-site PORT=9000       # 改 port
make -C backend openapi-site OUT=/tmp/site   # 改輸出路徑（此時 URL 為 /）
```

## 開發前檢查

在 repo 根目錄執行 `make -C backend fix` 自動修正 backend Python；送出 PR 前執行 `make -C backend check`，確認 Ruff、格式、`db-migration-check`，以及快速後端測試都通過。CI 會分開跑 Ruff 與 `db-migration-check`；pre-commit 在變更 `backend/alembic/` 時也會跑 `db-migration-check`。

## 資料庫遷移
**要修改資料庫前，請先告知其他人改動的欄位並進行討論。**

連線字串自動讀取 `config.py` 的 `DATABASE_URL`。  
新增的 model 需在 `app/models/__init__.py` import，autogenerate 才偵測得到。  

`APP_ENV=development` 時，啟動 FastAPI 會自動 upgrade head。  

請用 Make 目標（內部走 `scripts/run_alembic.py`），**不要**直接跑 `alembic` / `uv run alembic`：Alembic 1.20 用系統 locale 讀 `alembic.ini`，在 Windows CP950 下會因 UTF-8 繁中註解失敗。

```bash
make -C backend db-revision message="描述變更"   # autogenerate，產生後請人工檢查
make -C backend db-upgrade                        # upgrade head
make -C backend db-downgrade                      # 退回一版
make -C backend db-current                        # 目前 DB revision
make -C backend db-heads                          # 目前 migration head（應只有一個）
make -C backend db-migration-check                # 檢查是否對齊 origin/main
```

## Python 環境
請不要直接使用 python 或 python3 指令，用 `uv run <.py file>`。這樣才會使用 uv 的建立環境
要新增修改任何套件，也請使用 uv 操作，不要直接使用 pip

## AI Prompt 與對話上下文

所有模型工作的 system prompt 放在 `app/core/prompts/*.toml`，由 `app/core/prompts.py` 依 stage 載入，例如 `dialogue`、`validity`、`status`、`personal_report` 與 `class_summary`。修改 prompt 文字時，請在同一個變更中更新該檔的 `version`，並保留文末的「版本：…」字面值與現有 strict JSON schema。版本字串格式為 `<stage>-<描述>-<版本>`，例如 `stage1-validated-complete-3.2.0`。

成功生成結果的 prompt 版本存在各表的 `generation_meta`（JSONB）欄位中，內容為 `{prompt_stage, prompt_version}`。`sessions.generation_meta.context_summary` 保存滾動摘要 checkpoint（摘要文字、已涵蓋訊息數與產生它的 prompt 版本）。舊資料沒有這些細節時為 NULL。學生回覆存於 assistant 的 `DialogueMessage`，設定生成存於 `InquiryRevision`，背景報告與班級摘要則存於各自的 attempt。完整對話仍保存在 `DialogueMessage`；若上下文超出預算，`Session` 只額外保存目前的摘要 checkpoint 和已涵蓋訊息數，舊訊息不會刪除。

`DIALOGUE_CONTEXT_TOKEN_BUDGET` 預設為 12,000，計算 system prompt、對話資料、strict schema、訊息格式、安全餘裕和輸出 token 預留。估算使用 `tiktoken`，依實際傳給 provider 的模型 ID 選擇明確 tokenizer 對照；沒有對照的模型會在 provider 呼叫前被拒絕。新增或更換可用模型時，請先在 `app/services/token_budget.py` 補上並驗證 tokenizer 對照。各 stage 的輸出上限由 prompt registry 設定。

Prompt 和 tokenizer 在應用程式行程內載入；PostgreSQL 保存完整 transcript、prompt 來源 metadata 和目前摘要 checkpoint。此流程不使用 Redis 作為對話資料或 prompt 快取，之後若要加快速度，先依實際流量與 profiling 找出瓶頸。

## Stage 2 對話流程

每個學生回合依序執行三個模型階段（`app/services/dialogue_turn.py`）：

1. **validity**：判斷學生回答是否切題並說明理由（YES / NO）。NO 時只呼叫這一次，回覆為固定的離題訊息（`app/core/dialogue_messages.toml`），不呼叫後兩個階段。
2. **status**：產生這一回合的完整 progress 快照。
3. **planning**：產生可見回覆與提問方式（`present_counterexample` 或 `change_one_condition`）。

就緒由伺服器判定（`app/services/dialogue_progress.py`），不由模型決定。`goal_reached` 為真，需同時符合：

- 至少 3 個學生回合；
- 四個里程碑（position、reason、examination、response）都已達成，且每個證據都指向目前或之前的學生回合；
- response 在 examination 之後；
- 模型在 status 回報 `ready`。

儲存方式：

- `sessions.generation_meta.progress`：最新的 progress 快照。
- `dialogue_messages.generation_meta.analysis`：每則 AI 回覆的 move、status、safetyLevel，以及各階段的 prompt 版本。
- 寫入前 `save_exchange` 會先 `SELECT … FOR UPDATE` 鎖住 session，progress 與 goal 的更新在同一交易內序列化。

既有 session 沒有 progress：在它的第一個新回合前，會呼叫一次 status，對整段對話（附 exchange 編號）做補算，之後照常運作。這個補算每個 session 只做一次。

## 模型設定

- `OPENAI_MODEL` 預設為 `openai/gpt-6.1-sol`。所有課程 AI 工作（包含 validity、個人報告、班級摘要）優先使用題目所選模型，未設定才用此預設。`OPENAI_VALIDITY_MODEL` 僅保留設定相容性，不再覆蓋題目模型。
- 各任務的 timeout 與 `max_tokens` 上限（`app/services/model_client.py`）：
  - 課程設定（`inquiry_setup`）：45 秒，上限 2400 tokens；推理模型送 `reasoning: {effort: low}`。
  - 其他任務：60 秒，上限 4500 tokens。
  - 呼叫端可以要求更小的值，不能超過上限。超時會拋出 `ModelTimeoutError`。
- `REASONING_MODELS`：模型目錄中的 8 個 OpenAI 模型。2026-11-20 於 OpenRouter 公開模型清單確認，這 8 個都列出 `reasoning` 參數。
- 對話回覆使用 topic 上設定的模型，沒有才使用 `OPENAI_MODEL`。

## 個人報告的 progress 快照

- `report_attempts.generation_meta.progress` 在建立 attempt 時寫入當下的 `sessions.generation_meta.progress`。之後對話再變動，報告的依據不會改變。只有建立新 attempt 時才會取新快照；教師 retry 對 ready 或有效的執行中 attempt 會沿用，不強制重新產生。
- 沒有快照的 attempt（舊資料，或從未有 progress 的對話）只根據對話紀錄產生報告，快照欄位為 `NULL`。

## 尚未實作與刻意的設計選擇

- 離題回覆不顯示模型的內部推理（`thinkingProgress`），只顯示固定的說明文字。
- `safety_interruption` 與 `student_requested_stop` 尚未結束對話。`sessions.outcome` 目前有 CHECK 約束，新增 `interrupted` 需要先決定 migration 方式。
- 報告 schema 尚未映射新欄位，`ReportBody` 的形狀不變。

## 已知限制（部署前需處理）

- **tokenizer 估計限制**：目前八個 catalog 模型皆有 o200k_base 對照，因此預設 Luna 的缺少對照錯誤已修正。此對照仍為估計，未證明與 provider token 計數完全相同；openai/gpt-6-sol 尚未加入 catalog／對照。
- 既有 session 的 progress 補算只在它的下一個新回合發生；既有 report attempt 不會回補快照。

## 課程設定（Stage 1）

- 建立 topic 時，課程描述在模型呼叫前經過守門（`app/services/teacher_input.py`）：長度 20 到 6000 字；拒絕鍵盤序列、重複填充、沒有字母的文字，以及單一字母佔比過高的內容。不通過回 422，不呼叫模型。
- 模型輸出的 topic、core_question、inquiry_focus 若為占位值（未指定、N/A 等），回 503，不儲存。
- 背景或排除事項未指定時，回應的 `warnings` 會提醒教師在核准前確認。
- 課程設定超過 45 秒，回 504，教師的輸入保留在前端。
- 客戶端中止回 499 尚未實作。FastAPI 不會因為客戶端斷線而取消 handler，需要另外設計。

API transport, lifecycle and retry contracts: [integration guide](../docs/AI_BACKEND_CONTRACT.md).
