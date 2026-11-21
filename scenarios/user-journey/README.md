# User Journey Scenarios

對本機跑起來的後端做黑箱 API 驗證，以 [httpyac](https://httpyac.github.io/) 執行。結構沿用 [core-system-backend 的 scenarios](https://github.com/NYCU-SDC/core-system-backend/tree/main/scenarios)：每個 journey 一個資料夾，內含 `journey.yaml`、編號的 `.http` 檔、`.env.example` 與簡短 README。

> **只能對本機或開發環境執行。** Scenario 會註冊測試帳號、建立並刪除課程；需要 AI 的 journey 還會消耗 LLM 額度。不要把 `BASE_URL` 指到共用或正式環境。

## 安裝 httpyac

需要 httpyac 的 CLI。本 README 的指令以 6.16.7 驗證過。

**macOS（Homebrew）**

```sh
brew install httpyac
```

**Windows（PowerShell）**

httpyac 以 npm 套件發布，需要 Node.js 18 以上：

```powershell
# 已安裝 Node.js 18 以上可跳過這行
winget install OpenJS.NodeJS.LTS

# 安裝 Node.js 後重新開啟 PowerShell，讓 PATH 生效
npm install --global httpyac
```

**其他系統（例如 Linux）**：已有 Node.js 18 以上時，`npm install --global httpyac`。

**確認安裝成功**

```sh
httpyac --version
```

## 前置條件

1. 已安裝 httpyac（見上節）
2. 啟動 Postgres 與 Redis，並套用 migration：`make -C backend db-dev`、`make -C backend db-upgrade`
3. 灌入開發假資料，取得 seed 老師 `dev-teacher`：`make -C backend seed`（帳密見 [測試資料](../../docs/測試資料.md)）
4. 啟動後端：`make -C backend dev`
5. 在要執行的 journey 資料夾，把 `.env.example` 複製成 `.env`（`.env` 已被 git 忽略）
6. 需要 AI 的 journey（`topic-lifecycle`、`negative-topic-lifecycle`）還需要後端有可用的 LLM 設定：伺服器的 `OPENAI_API_KEY`，或老師自己的 key。未設定時只有這兩組會失敗，其餘不受影響

## 環境變數

| 變數 | 說明 |
| --- | --- |
| `BASE_URL` | API 位址，含 `/api/v1`，例如 `http://127.0.0.1:8000/api/v1` |
| `TEACHER_ACCOUNT_ID` | seed 老師帳號，預設 `dev-teacher` |
| `TEACHER_PASSWORD` | seed 老師密碼，見 [測試資料](../../docs/測試資料.md) |

## 如何執行

每個 case 對應 `journey.yaml` 的一筆 `cases`，以該筆的 `path` 與 `test` 執行：

```sh
httpyac send scenarios/user-journey/<journey>/<path> --name <test>
```

`--name` 指定的請求會連同它以 `# @ref` 依賴的前置請求一起執行，所以一個 case 通常涵蓋很多個請求。Smoke 則是：

```sh
httpyac send scenarios/smoke/health.http --all
```

## Journeys

| Journey | 性質 | 需要 LLM |
| --- | --- | --- |
| `user-lifecycle` | 正面 | 否 |
| `topic-lifecycle` | 正面 | 是 |

各 journey 的 case 與指令見它自己的 README。

## `journey.yaml` 格式

```yaml
name: "Journey Name"
description: "Short summary of the journey."
cases:
  - name: "Case Name"
    description: "Short summary of what this case verifies."
    path: "NN-scenario.http"
    test: "finalAssertionName"
```

- `path`：同一資料夾內的 `.http` 檔
- `test`：該檔內 `# @name` 的值，通常是整條鏈的最後一個請求

## 共用步驟

`shared/common.http` 提供各 journey 共用的註冊與登入請求：seed 老師、學生 A、學生 B、助教候選人、局外人。

- 學生、助教、局外人每次執行都用帶隨機字尾的新帳號，重跑不會因帳號已存在而失敗。後端沒有一般使用者可用的刪帳號途徑，所以本機資料庫會累積測試帳號；需要乾淨時用 `make -C backend db-reset`。
- 登入請求會匯出 `<角色>Token`（`Authorization` 標頭的完整 `Bearer …` 值），其他請求以 `Authorization: {{<角色>Token}}` 使用。
- 註冊、登入與目前使用者的回應都沒有使用者 ID；ID 取自指派助教與成員名單的回應。
- httpyac 每次執行只有一個 cookie jar，且只保留**最後一次登入**的 cookie。後端對 GET 與 HEAD 在 bearer 失效時會用 refresh cookie 靜默續期，所以不能帶任何先前登入 cookie 的請求要加 `# @no-cookie-jar`。
