Production Deploy Guideline

Please follow this order:

Database (Must be first to create docker network):
1. At `/devops/prob`, add `db_default_user_passwor.txt`, and put your default postgres password at the first line.

2. 
```
make -C devops db-prod
```

Backend:
1. At `/backend/.env`, followed by `/backend/.env.example`
2. Sync DB alembic version
```
make -C backend db-upgrade
```
2.
To update backend to newer version
```
make -C devops backend-prod-build
```

To restart current version
```
make -C devops backend-prod
```

Frontend:
1.
```
make -C devops frontend-prod-build
```

1. check if there is new build in `/frontend/dist`.

Nginx:
1.
```
make -C devops nginx-prod
```

To check containers
```
docker ps
```

open your local browser and type: `https://squicrates.ssr.ntnu.cc`
