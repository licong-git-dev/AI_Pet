# PetPal 部署手册（aliyun-lc-server-43）

目标主机
- IP: `8.136.34.43`
- 主机名: `aliyun-lc-server-43`
- 用户: `root`
- 操作系统假设: Ubuntu 22.04 / Aliyun Linux 3（按需调整）

> ⚠️ 本文档假设你已通过 ssh 登录到目标机。
> 凭证在团队内部 1Password / 飞书密码库另行托管，不在 git。

---

## 0. 准备：一次性安装基础组件

```bash
# Ubuntu / Debian
apt-get update
apt-get install -y curl git docker.io docker-compose-plugin python3.11 python3.11-venv build-essential ffmpeg

# 启用 docker 自启动
systemctl enable --now docker
```

如果是 Aliyun Linux：

```bash
yum install -y git docker python3.11 ffmpeg
systemctl enable --now docker
# 安装 docker compose 插件
mkdir -p ~/.docker/cli-plugins
curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
```

---

## 1. 拉代码

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/licong-git-dev/AI_Pet.git petpal
cd petpal
```

---

## 2. 配置环境变量

```bash
cp .env.docker.example backend/.env
vi backend/.env   # 填入 JWT/SECRET/DASHSCOPE/GEMINI/OPENAI keys
```

最少要把这些填上：
- `JWT_SECRET_KEY` / `SECRET_KEY` — 用强随机字符串
- `DASHSCOPE_API_KEY` — 通义千问，宠物诊断 / 分身对话主链路必须
- `GEMINI_API_KEY`（推荐）+ `OPENAI_API_KEY`（推荐）— 长期记忆 / 周摘要 / Wrapped 月报

可选：
- `MQTT_ENABLED=true` + `MQTT_HOST=localhost` 让桌宠 / 全息驱动真发 MQTT

---

## 3. 起后端 + 数据库 + 前端（主栈）

```bash
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose logs -f backend
```

- 后端: `http://8.136.34.43:8000`
- 前端: `http://8.136.34.43` (nginx 80)
- API 文档: `http://8.136.34.43:8000/docs`

---

## 4. 起可观测栈（可选）

```bash
cd docker/observability
docker compose up -d
```

- Prometheus: `http://8.136.34.43:9090`
- Grafana:    `http://8.136.34.43:3000` (admin / petpal-grafana)
- 默认仪表盘 `PetPal · 三大支柱总览` 已自动 provision

如果后端跑在同台主机，prometheus.yml 里 `host.docker.internal` 在 Linux 默认指向不到，
请改成 `8.136.34.43:8000` 或 `172.17.0.1:8000`（默认 docker bridge 网关）。

---

## 5. 起 MQTT broker（可选，桌宠 demo 联调时需要）

```bash
docker run -d --name mosquitto \
  -p 1883:1883 \
  --restart unless-stopped \
  eclipse-mosquitto:2 \
  mosquitto -c /mosquitto-no-auth.conf
```

然后在 `backend/.env` 设 `MQTT_ENABLED=true`，重启后端。

---

## 6. 录 Wrapped demo 视频（可选）

需要一台有显示驱动 / xvfb 的机器，云上 headless chromium 也可以：

```bash
cd /opt/petpal/tools/wrapped_video
npm install
npx playwright install --with-deps chromium
FRONTEND_URL=http://localhost:5173 node record.mjs
# 输出：dist/wrapped-demo.mp4
```

---

## 7. 升级流程

```bash
cd /opt/petpal
git pull
docker compose build backend frontend
docker compose up -d
docker compose exec backend alembic upgrade head
```

---

## 8. 排查

| 现象 | 可能原因 | 解决 |
| --- | --- | --- |
| `/metrics` 返回 404 | `prometheus-fastapi-instrumentator` 没装 | `docker compose exec backend pip install prometheus-fastapi-instrumentator` 后重启 |
| Wrapped 月报永远空 | 用户尚无 OwnerSignal 数据 | 让用户先用一次对话；月报会取上一个月 |
| Gemini 调用 503 | 区域限流 | 路由器会自动 failover 到 OpenAI；持续 503 检查代理 |
| Live2D 加载白屏 | 前端 `public/live2d/` 缺模型 | `cd frontend && npm run fetch:live2d` |
| 桌宠客户端 4001 关闭 WS | 后端 token 失效 | App 重新登录拿新 access_token |

---

## 9. 安全清单（上生产前必看）

- [ ] `JWT_SECRET_KEY` / `SECRET_KEY` 已替换为强随机
- [ ] `DEBUG=false`
- [ ] 数据库 root 密码已改且没暴露公网
- [ ] `/metrics` 在公网部署时挂 nginx basic-auth 或 IP 白名单
- [ ] Grafana admin 密码改掉
- [ ] 阿里云安全组只放 80/443，不要直接放 3000/9090/1883
