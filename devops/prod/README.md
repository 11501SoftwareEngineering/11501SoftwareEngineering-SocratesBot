Production Deploy Guideline

Please follow this order:

Database (Must be first to create docker network):
1. At `/devops/prob`, add `db_default_user_passwor.txt`, and put your default postgres password at the first line.

2. 
```
sudo make -C devops db-prod
```

Backend:
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

Frontend:
1.
```
sudo make -C devops frontend-prod-build
```

2. check if there is new build in `/frontend/dist`.

Nginx:
1.
```
sudo make -C devops nginx-prod
```

To check containers
```
sudo docker ps
```

open your local browser and type: `https://squicrates.ssr.ntnu.cc`
