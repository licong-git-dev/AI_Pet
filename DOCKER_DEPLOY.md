# PetPal Docker 部署指南

## 快速开始

### 1. 准备环境

确保已安装：
- Docker 20.10+
- Docker Compose 2.0+

### 2. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.docker.example .env

# 编辑 .env 文件，填入实际配置
vim .env
```

**必须配置的变量：**
- `JWT_SECRET_KEY` - JWT密钥（使用强随机字符串）
- `SECRET_KEY` - 应用密钥
- `MYSQL_ROOT_PASSWORD` - MySQL root密码
- `MYSQL_PASSWORD` - MySQL用户密码

### 3. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 4. 初始化数据库

```bash
# 进入后端容器
docker-compose exec backend bash

# 运行数据库迁移
alembic upgrade head

# 或创建所有表（如果是全新数据库）
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
alembic stamp head
```

### 5. 访问应用

- 前端: http://localhost (或配置的 FRONTEND_PORT)
- API: http://localhost/api
- API文档: http://localhost/api/docs

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 80 | Vue3前端应用 |
| backend | 8000 (内部) | FastAPI后端 |
| celery-worker | - | 异步任务处理 |
| celery-beat | - | 定时任务调度 |
| mysql | 3306 | MySQL数据库 |
| redis | 6379 | Redis缓存/队列 |

## 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启单个服务
docker-compose restart backend

# 查看日志
docker-compose logs -f backend

# 进入容器
docker-compose exec backend bash
```

### 数据库操作

```bash
# 备份数据库
docker-compose exec mysql mysqldump -u root -p petpal > backup.sql

# 恢复数据库
docker-compose exec -T mysql mysql -u root -p petpal < backup.sql

# 运行迁移
docker-compose exec backend alembic upgrade head
```

### 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build

# 运行迁移（如有）
docker-compose exec backend alembic upgrade head
```

## 生产环境配置

### 1. 使用外部数据库

修改 `.env` 中的 `DATABASE_URL`:
```
DATABASE_URL=mysql+pymysql://user:password@your-rds-host:3306/petpal
```

并注释掉 `docker-compose.yml` 中的 mysql 服务。

### 2. 使用外部Redis

修改 `.env` 中的 Redis 配置:
```
REDIS_URL=redis://:password@your-redis-host:6379/0
CELERY_BROKER_URL=redis://:password@your-redis-host:6379/1
```

### 3. 配置HTTPS

推荐使用 Nginx 或 Traefik 作为反向代理处理HTTPS。

### 4. 配置CDN

1. 将 `frontend/dist` 上传到CDN
2. 修改 `nginx.conf` 中的静态资源路径

## 故障排除

### 服务无法启动

```bash
# 查看详细日志
docker-compose logs backend

# 检查容器状态
docker-compose ps -a
```

### 数据库连接失败

1. 确认 MySQL 容器已启动: `docker-compose ps mysql`
2. 检查数据库密码配置
3. 等待 MySQL 完全启动（首次可能需要30秒）

### Celery任务不执行

```bash
# 检查 celery-worker 日志
docker-compose logs celery-worker

# 检查 Redis 连接
docker-compose exec redis redis-cli ping
```

## 监控与日志

### 日志目录

- 后端日志: `/app/logs` (容器内)
- Nginx日志: `/var/log/nginx/`
- MySQL日志: 通过 `docker-compose logs mysql` 查看

### 资源监控

```bash
# 查看容器资源使用
docker stats

# 查看磁盘使用
docker system df
```

## 安全建议

1. **修改默认密码**: 确保所有密码使用强随机字符串
2. **限制端口暴露**: 生产环境只暴露必要端口
3. **配置防火墙**: 限制数据库和Redis端口访问
4. **定期备份**: 设置自动数据库备份
5. **更新镜像**: 定期更新基础镜像修复安全漏洞
