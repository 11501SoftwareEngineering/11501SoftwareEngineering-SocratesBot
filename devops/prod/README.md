# Production Deploy Guideline

## 一鍵部署

需要先準備：

- `backend/.env`：依照 `backend/.env.example`，`APP_ENV=production`
- `devops/prod/db_default_user_password.txt`：第一行放 PostgreSQL 密碼，與 `backend/.env` 的 `POSTGRES_PASSWORD` 相同

在 repo 根目錄執行：

```
git pull
sudo make -C devops deploy
```

第一次部署（還沒有 `socrates-cloudflared` 容器）需要用 `sudo -E` 帶入 tunnel 的 connector token（`eyJ` 開頭，不是 tunnel ID），之後 `deploy` 會沿用容器裡的 token。看到「貼上 tunnel token：」後貼上 token（顯示為 `*`）再按 Enter，token 不會留在 shell history 或指令列：

```
cd ~/11501SoftwareEngineering-SocratesBot && CLOUDFLARE_TUNNEL_TOKEN="$(systemd-ask-password '貼上 tunnel token：')" && export CLOUDFLARE_TUNNEL_TOKEN && sudo -E make -C devops deploy
```

`deploy` 依序執行：

1. `prod-check`、`tunnel-check`：檢查 sudo、`backend/.env`（`APP_ENV`、DB 密碼一致、JWT/Teacher 金鑰）與 tunnel token，問題一次列出
2. `db-prod`：`db-network-prod` 網段不是 `10.200.200.0/24` 就重建、Redis volume 擁有者改為 999，啟動 PostgreSQL / Redis 並等待 healthy
3. `frontend-prod-build`：`frontend/dist` 改為 uid 1000 所有，build 並輸出
4. `backend-prod-deploy`：build 映像 → 容器內 `alembic upgrade head` → 重建並等待 healthy → nginx 在跑就 reload，重新解析 backend
5. `tunnel-prod`：重建 Cloudflare Tunnel
6. `nginx-prod`：重建 nginx（重新解析 backend、套用新的 `nginx.conf`）
7. `prod-status`：列出容器，檢查首頁與 nginx → backend → PostgreSQL/Redis，且沒有容器在 Restarting

每一步都可以單獨執行，例如只更新前端：`sudo make -C devops frontend-prod-build`。`sudo make -C devops db-prod-down` 會依序停掉 tunnel → nginx → backend → db；tunnel 容器刪掉後，下次部署要照第一次部署的方式帶入 token。

注意：

- 所有 compose 檔共用 project `prod`，orphan 警告已關閉，不要加 `--remove-orphans`（會停掉其他服務）
- 不要用 `down -v`，會刪掉 PostgreSQL 與 Redis 的資料
- backend 的 env 含 secrets，貼 log 時只 grep 錯誤行

## 單一步驟部署

Please follow this order:

### Database (Must be first to create docker network):
1. At `/devops/prob`, add `db_default_user_passwor.txt`, and put your default postgres password at the first line.

2. 
```
sudo make -C devops db-prod
```

3. One-time, only if the redis volume already exists and is owned by root (redis runs as uid 999). Confirm the volume name with `sudo docker volume ls` first (the project prefix is usually `prod_`):
```
sudo docker run --rm -v prod_redis_data_prod:/data alpine chown -R 999:999 /data
```

4. If `db-network-prod` already exists with a different subnet, stop the stack (`sudo make -C devops db-prod-down`), then bring it back up with `sudo make -C devops db-prod`. Restart nginx and the tunnel afterwards.

### Backend:
1. At `/backend/.env`, followed by `/backend/.env.example`
   
2. Sync DB alembic version (`alembic upgrade` is outside backend container, `POSTGRES_HOST` should be `127.0.0.1`, not `db` in `/backend/.env`)
```
POSTGRES_HOST=127.0.0.1 make -C backend db-upgrade
POSTGRES_HOST=127.0.0.1 make -C backend db-migration-check
```

3.
To update backend to newer version
```
sudo make -C devops backend-prod-build
```

To restart current version
```
sudo make -C devops backend-prod
```

### Frontend:
0. Before the first build on a new host, create the bind-mount directory owned by the `node` user (uid 1000), so Docker does not create it as root (run from the repo root):
```
mkdir -p frontend/dist && sudo chown 1000:1000 frontend/dist
```

1.
```
sudo make -C devops frontend-prod-build
```

2. check if there is new build in `/frontend/dist`.

### Nginx:
1.
```
sudo make -C devops nginx-prod
```

### To check containers
```
sudo docker ps
```

open your local browser and type: `https://squicrates.ssr.ntnu.cc`