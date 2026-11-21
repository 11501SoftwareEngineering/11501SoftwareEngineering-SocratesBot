FROM node:20-alpine

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --config.strict-dep-builds=false

COPY . .


ARG VITE_API_BASE_URL=http://localhost:80
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

ARG VITE_USE_MOCK=false
ENV VITE_USE_MOCK=${VITE_USE_MOCK}
RUN pnpm build

# 啟動時把編譯好的 dist 同步到共用 volume 后就結束
CMD ["sh", "-c", "rm -rf /localhost_frontend_dist/* && cp -r /app/dist/* /localhost_frontend_dist/"]
