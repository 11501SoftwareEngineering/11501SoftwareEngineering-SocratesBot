# Production Deploy Guideline

Please follow this order:

## Database (Must be first to create docker network):
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

## Backend:
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

## Frontend:
0. Before the first build on a new host, create the bind-mount directory owned by the `node` user (uid 1000), so Docker does not create it as root (run from the repo root):
```
mkdir -p frontend/dist && sudo chown 1000:1000 frontend/dist
```

1.
```
sudo make -C devops frontend-prod-build
```

2. check if there is new build in `/frontend/dist`.

## Nginx:
1.
```
sudo make -C devops nginx-prod
```

## To check containers
```
sudo docker ps
```

open your local browser and type: `https://squicrates.ssr.ntnu.cc`