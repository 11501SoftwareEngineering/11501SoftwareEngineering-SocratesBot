.PHONY:db
db:
		docker-compose -f ./devops/prod/docker-compose.db.yml up

.PHONY:db-down
db-down:
		docker-compose -f ./devops/prod/docker-compose.db.yml down
