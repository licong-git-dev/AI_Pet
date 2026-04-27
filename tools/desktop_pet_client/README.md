# PetPal 桌宠 / 树莓派客户端 demo

一个 ~250 行 Python 脚本，模拟桌面机器人 / 投影玩具的完整接入流程：

```
启动           → 调用 POST /devices/pair/start
打印 8 位配对码 → 主人在 App 上 POST /devices/pair/confirm
                 ↓
后端切到 online，开始定时心跳保活
                 ↓
分身一旦说话 → 后端通过 Orchestrator → MQTT publish
                 ↓
本客户端订阅 petpal/desktop_pet/{device_id}/cmd 收事件
                 ↓
渲染到终端"屏幕"（情绪 emoji + 说话文字 + 动画名）
```

## 安装

```bash
pip install -r requirements.txt
```

## 运行

最简（无 MQTT broker，仅跑 HTTP 闭环演示配对）：

```bash
python client.py --backend http://localhost:8000
```

完整链路（需要 MQTT broker，例如 mosquitto）：

```bash
python client.py \
  --backend http://localhost:8000 \
  --mqtt-host 127.0.0.1 \
  --mqtt-port 1883 \
  --device-id raspi-001 \
  --device-name "客厅小桌宠"
```

环境变量也可以：`PETPAL_BACKEND` / `PETPAL_MQTT_HOST` / `PETPAL_DEVICE_ID` 等。

## 后端要打开 MQTT 发布

在 `backend/.env` 里设置：

```
MQTT_ENABLED=true
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
```

后端启动时会日志 `MQTT publisher wired to AvatarRenderOrchestrator`。

## 起一个本地 MQTT broker（mosquitto）

```bash
docker run -d --name mosquitto \
  -p 1883:1883 \
  eclipse-mosquitto:2 \
  mosquitto -c /mosquitto-no-auth.conf
```

## 演示一次端到端

1. 启动后端 `uvicorn app.main:app --reload`
2. 启动本客户端，复制屏幕上的配对码
3. 在 App / curl 里调用：
   ```bash
   curl -X POST http://localhost:8000/api/v1/devices/pair/confirm \
     -H "Authorization: Bearer <YOUR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"pairing_code":"ABCD1234","pet_avatar_id":1}'
   ```
4. 用主人账户向分身说一句话（POST `/api/v1/pet-avatar/{pet_id}/chat`）
5. 桌宠终端会立刻打印 ASP 事件 + 渲染情绪/对话

## 真实硬件落地的扩展点

- 把 `render_event()` 替换成 SPI/I2C 驱动屏幕；动画名查表映射到舵机姿态
- 把 `print()` 关掉，改写到设备本地状态机
- BLE relay：本脚本的 MQTT 订阅 + 蓝牙转发既可
