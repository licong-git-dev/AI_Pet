"""
PetPal · 桌宠 / 树莓派客户端 demo

走通绑定全链路：
1. 启动 → 调用 /devices/pair/start 拿配对码
2. 在终端打印 8 位配对码（模拟桌宠 LCD 屏）
3. 等主人在 App 里调用 /devices/pair/confirm
4. 配对成功后开始定时心跳（保活）
5. 订阅 MQTT topic petpal/desktop_pet/{device_id}/cmd 收 ASP 事件并打印

使用：
    python client.py --backend http://localhost:8000 \
                     --mqtt-host localhost \
                     --device-id raspi-001 \
                     --device-name "客厅小桌宠"

依赖：requirements.txt
"""
import argparse
import json
import os
import signal
import sys
import threading
import time
import uuid
from typing import Optional

import requests

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[error] 需要先 pip install paho-mqtt", file=sys.stderr)
    sys.exit(2)


# ==================== ANSI 颜色 ====================

C_RESET = "\033[0m"
C_DIM = "\033[2m"
C_CYAN = "\033[96m"
C_YELLOW = "\033[93m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"


# ==================== ASCII 桌宠"屏幕" ====================

PET_FRAME_TOP = "┌─────────────────────┐"
PET_FRAME_BOT = "└─────────────────────┘"


def render_pet_screen(state: str, *lines: str) -> str:
    body = "\n".join(f"│ {line:<19} │" for line in (state, *lines))
    return f"\n{PET_FRAME_TOP}\n{body}\n{PET_FRAME_BOT}"


def emoji_for_emotion(emotion: Optional[str]) -> str:
    return {
        "happy": "(=^•ω•^=)",
        "sleepy": "(-_-) zzz",
        "loving": "(♡˘︶˘♡)",
        "sad": "(╥_╥)",
        "angry": "(>_<)",
        "surprised": "(O_O)!",
        "curious": "(◔_◔)?",
        "proud": "(¬‿¬)✧",
        "neutral": "(•_•)",
        "confused": "(•ิ_•ิ)?",
    }.get(emotion or "", "(•_•)")


# ==================== 客户端实现 ====================

class DesktopPetClient:
    HEARTBEAT_INTERVAL = 30.0

    def __init__(self, *, backend: str, mqtt_host: str, mqtt_port: int,
                 device_id: str, device_name: str, mqtt_user: Optional[str] = None,
                 mqtt_pass: Optional[str] = None):
        self.backend = backend.rstrip("/")
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.device_id = device_id
        self.device_name = device_name
        self.mqtt_user = mqtt_user
        self.mqtt_pass = mqtt_pass

        self.binding_id: Optional[int] = None
        self.pairing_code: Optional[str] = None
        self._mqtt: Optional[mqtt.Client] = None
        self._stop = threading.Event()

    # -------- HTTP 闭环 --------

    def start_pairing(self) -> dict:
        url = f"{self.backend}/api/v1/devices/pair/start"
        body = {
            "device_type": "desktop_pet",
            "device_id": self.device_id,
            "device_name": self.device_name,
            "capabilities": {"emotion": True, "animation": True, "speech": False},
            "transport": "mqtt",
        }
        r = requests.post(url, json=body, timeout=10)
        r.raise_for_status()
        data = r.json().get("data") or {}
        self.binding_id = data.get("binding_id")
        self.pairing_code = data.get("pairing_code")
        return data

    def heartbeat(self) -> bool:
        if not self.binding_id:
            return False
        url = f"{self.backend}/api/v1/devices/heartbeat"
        try:
            r = requests.post(url, json={"binding_id": self.binding_id}, timeout=8)
            return r.status_code == 200
        except requests.RequestException as e:
            print(f"{C_RED}[heartbeat] {e}{C_RESET}")
            return False

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            ok = self.heartbeat()
            mark = f"{C_GREEN}♥{C_RESET}" if ok else f"{C_RED}✗{C_RESET}"
            print(f"  {mark} heartbeat")
            self._stop.wait(self.HEARTBEAT_INTERVAL)

    # -------- MQTT --------

    def _on_connect(self, client, userdata, flags, rc):
        topic = f"petpal/desktop_pet/{self.device_id}/cmd"
        client.subscribe(topic, qos=0)
        print(f"{C_CYAN}[mqtt] connected, subscribed to {topic}{C_RESET}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            print(f"{C_RED}[mqtt] bad payload: {e}{C_RESET}")
            return
        self.render_event(payload)

    def render_event(self, payload: dict):
        """把 ASP 简化指令渲染到终端"""
        ev_type = payload.get("t", "?")
        emo = payload.get("emo")
        anim = payload.get("anim")
        txt = payload.get("txt") or ""
        ttl = payload.get("ttl_ms") or payload.get("ttl") or 0

        face = emoji_for_emotion(emo)
        head = f"{C_MAGENTA}● ASP event{C_RESET} type={ev_type} emo={emo} anim={anim} ttl={ttl}ms"
        body_lines = [face]
        if txt:
            body_lines.append(txt[:19])
            if len(txt) > 19:
                body_lines.append(txt[19:38])
        if anim:
            body_lines.append(f">> {anim}")
        screen = render_pet_screen(*body_lines[:5])
        print(head)
        print(C_YELLOW + screen + C_RESET)

    def start_mqtt(self):
        client_id = f"petpal-desktop-{self.device_id}-{uuid.uuid4().hex[:6]}"
        client = mqtt.Client(client_id=client_id, clean_session=True)
        if self.mqtt_user:
            client.username_pw_set(self.mqtt_user, self.mqtt_pass or "")
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        client.loop_start()
        self._mqtt = client

    # -------- 主循环 --------

    def run(self):
        # 1. 申请配对码
        try:
            self.start_pairing()
        except requests.RequestException as e:
            print(f"{C_RED}[pair.start] 后端不可达：{e}{C_RESET}")
            sys.exit(1)

        # 2. 显示配对码
        screen = render_pet_screen(
            "PetPal Pairing",
            "",
            f"  {self.pairing_code}",
            "",
            "Open App to confirm",
        )
        print(C_CYAN + screen + C_RESET)
        print(f"{C_DIM}binding_id = {self.binding_id}{C_RESET}")
        print(f"{C_DIM}backend  = {self.backend}{C_RESET}")
        print(f"{C_DIM}mqtt    = {self.mqtt_host}:{self.mqtt_port}{C_RESET}")
        print(f"\n{C_YELLOW}↳ 在 App 里调用 POST /api/v1/devices/pair/confirm 输入配对码完成绑定{C_RESET}\n")

        # 3. 心跳线程
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

        # 4. MQTT 订阅
        try:
            self.start_mqtt()
        except Exception as e:
            print(f"{C_RED}[mqtt] 连接失败：{e}{C_RESET}")
            print(f"{C_DIM}（可在没有 broker 时只跑 HTTP 闭环测试）{C_RESET}")

        # 5. 等终止
        signal.signal(signal.SIGINT, lambda *_: self._stop.set())
        signal.signal(signal.SIGTERM, lambda *_: self._stop.set())
        try:
            while not self._stop.is_set():
                time.sleep(0.5)
        finally:
            print(f"\n{C_DIM}shutting down...{C_RESET}")
            if self._mqtt:
                self._mqtt.loop_stop()
                self._mqtt.disconnect()


def parse_args():
    p = argparse.ArgumentParser(description="PetPal 桌宠 / 树莓派 demo 客户端")
    p.add_argument("--backend", default=os.getenv("PETPAL_BACKEND", "http://localhost:8000"))
    p.add_argument("--mqtt-host", default=os.getenv("PETPAL_MQTT_HOST", "localhost"))
    p.add_argument("--mqtt-port", type=int, default=int(os.getenv("PETPAL_MQTT_PORT", "1883")))
    p.add_argument("--mqtt-user", default=os.getenv("PETPAL_MQTT_USER"))
    p.add_argument("--mqtt-pass", default=os.getenv("PETPAL_MQTT_PASS"))
    p.add_argument("--device-id", default=os.getenv("PETPAL_DEVICE_ID", f"raspi-{uuid.uuid4().hex[:6]}"))
    p.add_argument("--device-name", default=os.getenv("PETPAL_DEVICE_NAME", "客厅小桌宠"))
    return p.parse_args()


def main():
    args = parse_args()
    client = DesktopPetClient(
        backend=args.backend,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        device_id=args.device_id,
        device_name=args.device_name,
        mqtt_user=args.mqtt_user,
        mqtt_pass=args.mqtt_pass,
    )
    client.run()


if __name__ == "__main__":
    main()
