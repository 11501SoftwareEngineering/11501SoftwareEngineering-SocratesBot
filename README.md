# 蘇格拉底對話機器人

## 環境需求

- Docker & Docker Compose

## 快速啟動

### 1. 複製環境變數設定檔
```bash
cp .env.example .env
```

### 2. 本地開發環境
```bash
docker compose up -d --build
```

### 3. 生產環境
```bash
docker compose -f docker-compose-prod.yml up -d --build
```

## 服務埠號一覽

| 服務 | 內部埠號 | 預設對外埠號 | 說明 |
| :--- | :--- | :--- | :--- |
| Backend API | 8000 | 8000 | FastAPI 伺服器 |
| PostgreSQL | 5432 | 5432 | 關聯式資料庫 |
| Redis | 6379 | 6379 | 快取與任務佇列 |