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
    cp devops/prod/db_default_user_password_example.txt devops/prod/db_default_user_password.txt
    ```
    > `POSTGRES_PASSWORD` 需與 `devops/prod/db_default_user_password.txt` 內容相同。

3. 建立 Python 虛擬環境與套件安裝
    ```bash
    cd backend
    uv sync
    ```
    uv 會讀取 pyproject.toml 與 uv.lock，建立虛擬環境 backend/.venv 並自動安裝套件。

## 啟動開發伺服器
1. 啟動 docker 容器，裡面有 PostgreSQL 和 Redis. 
    在專案根目錄執行：
    ```bash
    make db
    ```

    檢查容器狀態：
    ```bash
    docker compose ps
    ```

    關閉容器
    ```bash
    make db-down
    ```

2. 啟動 fastapi
到後端資料夾下執行
```bash
uv run fastapi dev app/main.py
```
API 文件:
http://localhost:8000/docs 
http://localhost:8000/redoc

確認 PostgreSQL 與 Redis 連線狀態:
http://localhost:8000/api/v1/health

## 資料庫遷移
**要修改資料庫前，請先告知其他人改動的欄位並進行討論。**

在 `backend/` 下執行，連線字串自動讀取 `.env` 的 `DATABASE_URL`。  
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