import paho.mqtt.client as mqtt
import time
import threading
import matplotlib.pyplot as plt
import ssl
from publisher.temperature import TemperaturePublisher
from publisher.lighting import LightingPublisher
from publisher.security import SecurityPublisher
from schedule import SchedulerPublisher, SchedulerSubscriber
from ui import SmartHomeUI
import tkinter as tk
import json
import sqlite3
from datetime import datetime, timedelta
import queue

# 配置常量（与其他模块一致）
BROKER = 'test.mosquitto.org'
PORT = 8883
TEMPERATURE_TOPIC = "home/sensor/temperature"
LIGHTING_TOPIC = "home/sensor/lighting"
SECURITY_TOPIC = "home/security/status"


class SmartHomeSystem:
    def __init__(self):
        # 初始化MQTT客户端
        self.client = mqtt.Client(
            client_id="SmartHomeSystem",
            # callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            # paho-mqtt版本1.6.0不需要这行配置，版本1.5.0及以下需要
            protocol = mqtt.MQTTv311  # 明确指定协议版本
        )
        
        try:
            self.client.tls_set(
                ca_certs="mosquitto.org.crt",
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            self.client.tls_insecure_set(True)
        except Exception as e:
            print(f"TLS配置错误: {e}")
            raise

        # 设置回调
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # 初始化发布者
        self.temp_pub = TemperaturePublisher(self.client)
        self.light_pub = LightingPublisher(self.client)
        self.security_pub = SecurityPublisher(self.client)
        
        # 初始化定时任务发布者和订阅者
        self.scheduler_pub = SchedulerPublisher(self.client)
        self.scheduler_sub = SchedulerSubscriber(self.client, self.on_schedule_update)

        # 初始化数据库
        self.setup_database()

        # 创建Tkinter根窗口（但不立即显示）
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口

        self.app = None
        self.setup_database_maintenance()
        
        # 消息队列用于线程安全更新UI
        self.ui_queue = queue.Queue()

    def setup_database_maintenance(self):
        """设置数据库定期维护"""

        def db_maintenance():
            while True:
                self.optimize_database()
                time.sleep(86400)  # 每天执行一次

        threading.Thread(target=db_maintenance, daemon=True).start()

    def optimize_database(self):
        """优化数据库性能并清理旧数据"""
        conn = sqlite3.connect('smart_home.db')
        try:
            cursor = conn.cursor()

            # 保留最近30天数据
            cutoff = datetime.now() - timedelta(days=30)

            # 清理各表旧数据
            for table in ['temperature', 'lighting', 'security_status']:
                cursor.execute(f"DELETE FROM {table} WHERE timestamp < ?",
                               (cutoff.strftime('%Y-%m-%d %H:%M:%S'),))
            conn.commit()  # 先提交删除操作

            # 执行VACUUM优化
            cursor.execute("VACUUM")
            conn.commit()

            print("数据库维护完成: 清理旧数据并优化性能")
        except Exception as e:
            print(f"数据库维护错误: {e}")
        finally:
            conn.close()

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Connected to MQTT Broker!")
            # 订阅所有需要的主题
            client.subscribe(TEMPERATURE_TOPIC, qos=1)  # 温度
            client.subscribe(LIGHTING_TOPIC, qos=1)  # 照明
            client.subscribe(SECURITY_TOPIC, qos=2)  # 安全
        else:
            print(f"Connection failed with code {rc}")

    def on_message(self, client, userdata, msg):
        """处理所有订阅消息"""
        try:
            payload = msg.payload.decode()
            topic = msg.topic

            # 尝试解析JSON，如果失败则作为原始数据处理
            try:
                data = json.loads(payload)
                if not isinstance(data, dict):  # 如果不是字典，转换为标准格式
                    if topic == TEMPERATURE_TOPIC:
                        data = {"temperature": float(data), "comfort_level": "optimal"}
                    elif topic == LIGHTING_TOPIC:
                        data = {"brightness": int(data), "camera_mode": "auto"}
                    elif topic == SECURITY_TOPIC:
                        data = {"lock_status": "locked" if bool(data) else "unlocked",
                                "noise_reduction": "enabled"}
            except json.JSONDecodeError:
                # 如果不是JSON，根据主题转换为相应格式
                if topic == TEMPERATURE_TOPIC:
                    data = float(payload)
                elif topic == LIGHTING_TOPIC:
                    data = int(payload)
                elif topic == SECURITY_TOPIC:
                    data = bool(payload)

            # 根据主题路由到不同处理逻辑
            if topic == TEMPERATURE_TOPIC:
                self.handle_temperature_data(data)
                # 传递给UI
                if hasattr(self, 'ui_queue'):
                    self.ui_queue.put(("update_temperature", data))
            elif topic == LIGHTING_TOPIC:
                self.handle_lighting_data(data)
                if hasattr(self, 'ui_queue'):
                    self.ui_queue.put(("update_lighting", data))
            elif topic == SECURITY_TOPIC:
                self.handle_security_data(data)
                if hasattr(self, 'ui_queue'):
                    self.ui_queue.put(("update_security", data))

        except Exception as e:
            print(f"Error processing message on {msg.topic}: {e}")

    def handle_temperature_data(self, data):
        """处理温度数据并存入数据库"""
        if isinstance(data, (int, float)):
            data = {"temperature": data, "comfort_level": "optimal"}

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

    def on_schedule_update(self, data):
        """处理定时任务更新消息"""
        # 如果UI已初始化，则通知UI更新定时任务
        if hasattr(self, 'ui_queue'):
            self.ui_queue.put(("update_schedule", data))

    def start_ui(self):
        """启动UI界面"""
        # 确保在主线程中创建UI
        def _start_ui():
            # 创建UI实例
            self.app = SmartHomeUI(self.root)
            
            # 传递必要的对象给UI
            self.app.mqtt_client = self.client
            self.app.scheduler_pub = self.scheduler_pub
            self.app.ui_queue = self.ui_queue
            
            # 显示主窗口
            self.root.deiconify()
            self.app.run()

        if threading.current_thread() is threading.main_thread():
            _start_ui()
        else:
            self.root.after(0, _start_ui)

    def run(self):
        """Main execution loop"""
        try:
            # 连接MQTT
            self.client.connect(BROKER, PORT, 60)
            self.client.loop_start()
            
            # 启动定时任务调度器
            self.scheduler_pub.start()

            # 在主线程创建UI
            self.root.deiconify()
            self.app = SmartHomeUI(self.root)
            
            # 传递必要的对象给UI
            self.app.mqtt_client = self.client
            self.app.scheduler_pub = self.scheduler_pub
            self.app.ui_queue = self.ui_queue

            # 在主线程中启动UI
            self.start_ui()

            # 设置定时发布
            self.setup_publish_timer()

            # 进入主循环
            self.root.mainloop()

        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
        except ssl.SSLError as e:
            print(f"SSL错误: {e}")
            # 处理证书验证失败等情况
        except Exception as e:
            print(f"错误: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            
            # 停止定时任务调度器
            self.scheduler_pub.stop()
            
            if hasattr(self, 'root') and self.root:
                self.root.quit()

    def publish_loop(self):
        """独立的发布循环"""
        while True:
            self.temp_pub.publish()
            self.light_pub.publish()
            self.security_pub.publish()
            time.sleep(10)

    def shutdown(self):
        """关闭应用程序"""
        if hasattr(self, 'root') and self.root:
            self.root.quit()
        if hasattr(self, 'client') and self.client:
            self.client.disconnect()
            
        # 停止定时任务调度器
        if hasattr(self, 'scheduler_pub'):
            self.scheduler_pub.stop()
            
        plt.close('all')
        if hasattr(self, 'conn'):
            self.conn.close()

    def setup_publish_timer(self):
        """设置定期发布数据的定时器"""

        def publish():
            try:
                self.temp_pub.publish()
                self.light_pub.publish()
                self.security_pub.publish()
            except Exception as e:
                print(f"Publish error: {e}")
            finally:
                # 10秒后再次执行
                self.root.after(10000, publish)

        # 立即开始
        self.root.after(0, publish)


if __name__ == "__main__":
    # 创建系统实例
    system = SmartHomeSystem()

    try:
        # 运行系统
        system.run()
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    finally:
        # 确保资源清理
        system.shutdown()
