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
    ```

3. 在 repo 根目錄安裝鎖定的 Python 套件並啟用 pre-commit：
    ```bash
    make -C backend setup
    ```
    `make -C backend setup` 會依 `backend/uv.lock` 安裝套件並安裝 Git hook。提交時 Ruff 會修正 backend Python 的 lint 與格式問題，Gitleaks 會掃描整個 repo 的 staged 內容。

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

## 開發前檢查

在 repo 根目錄執行 `make -C backend fix` 自動修正 backend Python；送出 PR 前執行 `make -C backend check`，確認 Ruff、格式與快速後端測試都通過。CI 會以唯讀方式重跑檢查。

## 資料庫遷移
**要修改資料庫前，請先告知其他人改動的欄位並進行討論。**

在 `backend/` 下執行，連線字串自動讀取 `config.py` 的 `DATABASE_URL`。  
新增的 model 需在 `app/models/__init__.py` import，autogenerate 才偵測得到。  

`APP_ENV=development` 時，啟動 FastAPI 會自動 upgrade head。  

```bash
# 依 models 變更產生 migration 腳本（產生後請檢查內容）
uv run alembic revision --autogenerate -m "描述"

# 套用到最新版本
uv run alembic upgrade head

# 退回上一版
uv run alembic downgrade -1

# 查看目前版本
uv run alembic current
```

## Python 環境
請不要直接使用 python 或 python3 指令，用 `uv run <.py file>`。這樣才會使用 uv 的建立環境
要新增修改任何套件，也請使用 uv 操作，不要直接使用 pip
