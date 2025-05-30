import paho.mqtt.client as mqtt
import time
import threading
from publisher.temperature import TemperaturePublisher
from publisher.lighting import LightingPublisher
from publisher.security import SecurityPublisher
from ui import SmartHomeUI
import tkinter as tk
import json
import sqlite3

# 配置常量（与其他模块一致）
BROKER = 'test.mosquitto.org'
PORT = 1883
TEMPERATURE_TOPIC = "home/sensor/temperature"
LIGHTING_TOPIC = "home/sensor/lighting"
SECURITY_TOPIC = "home/security/status"


class SmartHomeSystem:
    def __init__(self):
        # 初始化MQTT客户端
        self.client = mqtt.Client(client_id="SmartHomeSystem")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # 初始化发布者
        self.temp_pub = TemperaturePublisher(self.client)
        self.light_pub = LightingPublisher(self.client)
        self.security_pub = SecurityPublisher(self.client)

        # 初始化数据库
        self.setup_database()

        # 启动UI线程
        self.ui_thread = threading.Thread(target=self.start_ui, daemon=True)
        self.ui_thread.start()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            # 订阅所有需要的主题
            client.subscribe(TEMPERATURE_TOPIC)
            client.subscribe(LIGHTING_TOPIC)
            client.subscribe(SECURITY_TOPIC)
        else:
            print(f"Connection failed with code {rc}")

    def on_message(self, client, userdata, msg):
        """处理所有订阅消息"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic

            # 根据主题路由到不同处理逻辑
            if topic == TEMPERATURE_TOPIC:
                self.handle_temperature_data(payload)
            elif topic == LIGHTING_TOPIC:
                self.handle_lighting_data(payload)
            elif topic == SECURITY_TOPIC:
                self.handle_security_data(payload)

        except json.JSONDecodeError:
            print(f"Invalid JSON data received on {msg.topic}")

    def handle_temperature_data(self, data):
        """处理温度数据并存入数据库"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO temperature (temperature, comfort_level) VALUES (?, ?)",
            (data['temperature'], data['comfort_level'])
        )
        conn.commit()
        conn.close()

    def handle_lighting_data(self, data):
        """处理照明数据并存入数据库"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO lighting (brightness, camera_mode) VALUES (?, ?)",
            (data['brightness'], data['camera_mode'])
        )
        conn.commit()
        conn.close()

    def handle_security_data(self, data):
        """处理安全数据并存入数据库"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO security_status (lock_status, noise_reduction) VALUES (?, ?)",
            (data['lock_status'], data['noise_reduction'])
        )
        conn.commit()
        conn.close()

    def setup_database(self):
        """初始化数据库表结构（与文档3一致）"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS temperature (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        temperature REAL,
                        comfort_level TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS lighting (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        brightness INTEGER,
                        camera_mode TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS security_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lock_status TEXT,
                        noise_reduction TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        conn.commit()
        conn.close()

    def start_ui(self):
        """启动UI界面"""
        root = tk.Tk()
        app = SmartHomeUI(root)
        app.run()

    def run(self):
        """主运行循环"""
        # 连接MQTT代理
        self.client.connect(BROKER, PORT, 60)
        self.client.loop_start()

        try:
            while True:
                # 定期发布传感器数据
                self.temp_pub.publish()
                self.light_pub.publish()
                self.security_pub.publish()

                time.sleep(10)  # 每10秒发布一次

        except KeyboardInterrupt:
            print("Shutting down...")
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    system = SmartHomeSystem()
    system.run()