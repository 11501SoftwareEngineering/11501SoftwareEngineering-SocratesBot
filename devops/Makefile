# production deployment: sudo make -C devops deploy

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.NOTPARALLEL:
export COMPOSE_IGNORE_ORPHANS := 1

ifeq ($(CLOUDFLARE_TUNNEL_TOKEN)$(wildcard prod/.env),)
CLOUDFLARE_TUNNEL_TOKEN := $(shell docker inspect socrates-cloudflared --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | sed -n 's/^TUNNEL_TOKEN=//p')
ifneq ($(CLOUDFLARE_TUNNEL_TOKEN),)
export CLOUDFLARE_TUNNEL_TOKEN
endif
endif

.PHONY: deploy
deploy: prod-check tunnel-check db-prod frontend-prod-build backend-prod-deploy tunnel-prod nginx-prod prod-status

.PHONY: prod-check
prod-check: prod/db_default_user_password.txt ../backend/.env
	@get() { sed -n "s/^[[:space:]]*$$2[[:space:]]*=[[:space:]]*//p" "$$1" 2>/dev/null | tail -n 1 | tr -d "\"'\r"; }; \
	errors=(); \
	docker info >/dev/null 2>&1 || errors+=("無法連線 Docker daemon，請用 sudo 執行"); \
	case "$$(get ../backend/.env APP_ENV)" in development|test|"") errors+=("backend/.env：APP_ENV 必須是 production");; esac; \
	[ "$$(get ../backend/.env POSTGRES_PASSWORD)" = "$$(cat prod/db_default_user_password.txt)" ] || errors+=("backend/.env：POSTGRES_PASSWORD 與 devops/prod/db_default_user_password.txt 不一致"); \
	for key in JWT_SECRET_KEY TEACHER_API_KEY_SECRET; do \
	  val="$$(get ../backend/.env $${key})"; \
	  if [ $${#val} -lt 32 ] || [ "$${val#change_me}" != "$${val}" ]; then errors+=("backend/.env：$${key} 未設定或仍是範例值（openssl rand -hex 32）"); fi; \
	done; \
	if [ $${#errors[@]} -gt 0 ]; then printf '[error] %s\n' "$${errors[@]}" >&2; exit 1; fi

.PHONY: tunnel-check
tunnel-check:
	@token="$${CLOUDFLARE_TUNNEL_TOKEN:-$$(sed -n 's/^[[:space:]]*CLOUDFLARE_TUNNEL_TOKEN[[:space:]]*=[[:space:]]*//p' prod/.env 2>/dev/null | tail -n 1 | tr -d "\"'\r" || true)}"; \
	case "$${token}" in \
	  eyJ*) ;; \
	  "") echo "[error] 沒有 CLOUDFLARE_TUNNEL_TOKEN：找不到 socrates-cloudflared 容器，請照 devops/prod/README.md 的第一次部署方式帶入" >&2; exit 1;; \
	  *) echo "[error] CLOUDFLARE_TUNNEL_TOKEN 要用 connector token（eyJ 開頭），不是 tunnel ID" >&2; exit 1;; \
	esac

# cloudflared 只斷開不刪除：tunnel token 留在它的容器設定裡，中途失敗也能重跑
.PHONY: network-check
network-check:
	@subnet="$$(docker network inspect db-network-prod --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || true)"; \
	if [ -n "$${subnet}" ] && [ "$${subnet}" != 10.200.200.0/24 ]; then \
	  echo "==> db-network-prod 網段是 $${subnet}，移除掛在上面的容器並以 10.200.200.0/24 重建（volume 保留）"; \
	  docker network disconnect -f db-network-prod socrates-cloudflared 2>/dev/null || true; \
	  ids="$$(docker ps -aq --filter network=db-network-prod)"; \
	  if [ -n "$${ids}" ]; then docker rm -f $${ids}; fi; \
	  docker network rm db-network-prod; \
	fi

.PHONY: redis-volume-fix
redis-volume-fix:
	@if docker volume inspect prod_redis_data_prod >/dev/null 2>&1 \
	    && [ "$$(docker run --rm -v prod_redis_data_prod:/data alpine stat -c %u /data)" != 999 ]; then \
	  echo "==> prod_redis_data_prod 擁有者改為 999"; \
	  docker run --rm -v prod_redis_data_prod:/data alpine chown -R 999:999 /data; \
	fi

.PHONY: db-prod
db-prod: prod-check network-check redis-volume-fix
	docker compose -f prod/docker-compose.db.yml up -d --wait --wait-timeout 120

.PHONY: db-prod-down
db-prod-down: tunnel-prod-down nginx-prod-down backend-prod-down
	docker compose -f prod/docker-compose.db.yml down

.PHONY: db-dev
db-dev:
	docker compose -f dev/docker-compose.db.yml up

.PHONY: db-dev-down
db-dev-down:
	docker compose -f dev/docker-compose.db.yml down

.PHONY: backend-prod-deploy
backend-prod-deploy: prod-check
	docker compose -f prod/docker-compose.backend.yml run --rm --build --no-deps -T backend uv run --frozen python scripts/run_alembic.py upgrade head
	docker compose -f prod/docker-compose.backend.yml up -d --force-recreate --wait --wait-timeout 180
	@if [ "$$(docker inspect -f '{{.State.Running}}' socrates-nginx 2>/dev/null)" = true ]; then docker exec socrates-nginx nginx -s reload; fi

.PHONY: backend-prod-build
backend-prod-build:
	docker compose -f prod/docker-compose.backend.yml up -d --build

.PHONY: backend-prod
backend-prod:
	docker compose -f prod/docker-compose.backend.yml up -d

.PHONY: backend-prod-down
backend-prod-down:
	docker compose -f prod/docker-compose.backend.yml down

.PHONY: frontend-dist
frontend-dist:
	mkdir -p ../frontend/dist && chown -R 1000:1000 ../frontend/dist

.PHONY: frontend-prod-build
frontend-prod-build: frontend-dist
	docker compose -f prod/docker-compose.frontend.yml run --rm --build -T frontend-builder

# nginx.conf 寫壞會直接停機，需要時先跑 nginx -t 再重建。
.PHONY: nginx-prod
nginx-prod: frontend-dist
	docker compose -f prod/docker-compose.nginx.yml up -d --force-recreate

.PHONY: nginx-prod-down
nginx-prod-down:
	docker compose -f prod/docker-compose.nginx.yml down

.PHONY: tunnel-prod
tunnel-prod: tunnel-check
	docker compose -f prod/docker-compose.tunnel.yml up -d --force-recreate

# down 不需要 token，避免 :? 擋住
.PHONY: tunnel-prod-down
tunnel-prod-down:
	CLOUDFLARE_TUNNEL_TOKEN=unused docker compose -f prod/docker-compose.tunnel.yml down

.PHONY: prod-status
prod-status:
	docker ps --filter network=db-network-prod --format 'table {{.Names}}\t{{.Status}}'
	for i in 1 2 3 4 5; do docker exec socrates-nginx wget -q -O /dev/null http://127.0.0.1/ && docker exec socrates-nginx wget -q -O /dev/null http://127.0.0.1/api/v1/health && exit 0; sleep 2; done; exit 1
	@if [ -n "$$(docker ps -q --filter network=db-network-prod --filter status=restarting)" ]; then echo "[error] 有容器在 Restarting，請看 docker logs" >&2; exit 1; fi
