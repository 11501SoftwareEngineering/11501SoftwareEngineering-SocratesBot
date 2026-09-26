# Squicrates 後端
## 環境建置

1. 請確認本機已安裝以下工具：
    - Docker & Docker Compose
    - uv
    - Makefile

2. 複製環境設定檔：
    ```bash
    cp .env.example .env
    cp devops/prod/db_default_user_password_example.txt devops/prod/db_default_user_password.txt
    ```

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
到 http://localhost:8000 應該就可以看到了

## Python 環境
請不要直接使用 python 或 python3 指令，用 `uv run <.py file>`。這樣才會使用 uv 的建立環境
要新增修改任何套件，也請使用 uv 操作，不要直接使用 pip