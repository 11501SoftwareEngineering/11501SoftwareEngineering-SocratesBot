.PHONY:db-prod
db-prod:
		docker-compose -f ./prod/docker-compose.db.yml up -d

.PHONY:db-prod-down
db-prod-down:
		docker-compose -f ./prod/docker-compose.db.yml down

.PHONY:db-dev
db-dev:
		docker-compose -f ./dev/docker-compose.db.yml up

.PHONY:db-dev-down
db-dev-down:
		docker-compose -f ./dev/docker-compose.db.yml down

.PHONY:backend-prod-build
backend-prod-build:
		docker-compose -f ./prod/docker-compose.backend.yml up -d --build

.PHONY:backend-prod
backend-prod:
		docker-compose -f ./prod/docker-compose.backend.yml up -d

.PHONY:frontend-prod-build
frontend-prod-build:
		docker-compose -f ./prod/docker-compose.frontend.yml up -d --build


.PHONY:nginx-prod
nginx-prod:
		docker-compose -f ./prod/docker-compose.nginx.yml up -d
