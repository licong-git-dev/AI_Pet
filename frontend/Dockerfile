# PetPal 前端镜像 - Vite build → Nginx 静态托管
ARG VITE_API_BASE_URL=/api

# ==================== 1. build 阶段 ====================
FROM node:20-alpine AS builder
WORKDIR /app

# 强制 NODE_ENV=development 让 npm 一定装 devDeps（vue-tsc / vite / sass 都在 dev）
ENV NODE_ENV=development

# 利用层缓存：先装依赖
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund \
    && test -x node_modules/.bin/vite \
    && test -x node_modules/.bin/vue-tsc

# 拷源码并构建（直接走 .bin 路径，最可靠）
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN ./node_modules/.bin/vue-tsc --noEmit \
    && ./node_modules/.bin/vite build

# ==================== 2. runtime 阶段 ====================
FROM nginx:1.27-alpine AS runtime

# 自带 SPA 友好的 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 拷构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 健康检查端点
RUN echo "ok" > /usr/share/nginx/html/health

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
