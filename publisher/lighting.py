import paho.mqtt.client as mqtt
import json
import random
import numpy as np
import time
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from datetime import datetime
from sklearn.preprocessing import StandardScaler


class LightingPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/lighting"
        self.data = {
            "brightness": 80,
            "camera_mode": "auto"
        }
        self.previous_brightness = 80  # 添加前一个亮度值
        self.smoothing_factor = 0.3  # 平滑系数(0-1之间)

        # 新增的机器学习模型部分
        self.model = LinearRegression()
        self.history_data = [
            [20, 100], [30, 95], [40, 90], [50, 85],
            [60, 80], [70, 75], [80, 70], [90, 65]
        ]
        self.train_model()
        self.room_type = "living_room"  # 可配置为 bedroom/kitchen等
        self.occupancy = False
        self.last_motion_time = time.time()
        self.scaler = StandardScaler()

    def _simulate_real_lighting(self):
        now = datetime.now()
        hour = now.hour + now.minute / 60

        # 基础光照 (考虑昼夜变化)
        if 6 <= hour < 18:  # 白天
            base_light = 80 + 40 * np.sin(np.pi * (hour - 12) / 12)
        else:  # 夜晚
            base_light = 10 + 5 * np.sin(np.pi * (hour - 24) / 12)

        # 随机波动
        random_effect = np.random.randint(-5, 5)

        # 人体活动影响 (30%概率检测到活动)
        motion_effect = 0
        if np.random.random() < 0.3:
            self.occupancy = True
            self.last_motion_time = time.time()
            motion_effect = 30 + np.random.randint(0, 20)
        elif time.time() - self.last_motion_time > 300:  # 5分钟无活动
            self.occupancy = False

        # 房间类型调整
        room_adjustments = {
            'living_room': 5,
            'bedroom': -10,
            'kitchen': 15,
            'bathroom': 0
        }

        raw_brightness = base_light + random_effect + motion_effect + room_adjustments[self.room_type]

        # 应用平滑处理
        smoothed_brightness = (self.smoothing_factor * raw_brightness +
                               (1 - self.smoothing_factor) * self.previous_brightness)
        max_change = 5
        if abs(raw_brightness - self.previous_brightness) > max_change:
            if raw_brightness > self.previous_brightness:
                smoothed_brightness = self.previous_brightness + max_change
            else:
                smoothed_brightness = self.previous_brightness - max_change
        else:
            smoothed_brightness = raw_brightness

        # 更新前一个亮度值
        self.previous_brightness = smoothed_brightness

        return np.clip(smoothed_brightness, 0, 100)

    def train_model(self):
        hours = np.random.randint(0, 24, 1000)
        brightness = np.clip(80 + 30 * np.sin(np.pi * (hours - 12) / 12) + np.random.normal(0, 5, 1000), 0, 100)
        self.history_data = np.column_stack((hours, brightness))

        X = self.history_data[:, 0].reshape(-1, 1)
        y = self.history_data[:, 1]

        # 添加多项式特征
        from sklearn.preprocessing import PolynomialFeatures
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X)

        X_train, X_test, y_train, y_test = train_test_split(
            X_poly, y, test_size=0.2, random_state=42)

        self.model = LinearRegression()
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f"Lighting model MSE: {mse:.2f}")

    def predict_brightness_adjustment(self, ambient_light):
        if hasattr(self, 'scaler'):
            ambient_light_scaled = self.scaler.transform([[ambient_light]])
            return int(self.model.predict(ambient_light_scaled)[0])
        return int(self.model.predict([[ambient_light]])[0])

    def publish(self):
        ambient_light = np.random.randint(10, 100)
        self.data["brightness"] = self.predict_brightness_adjustment(ambient_light)
        self.data["camera_mode"] = random.choice(["auto", "manual", "off"])

        try:
            # QoS 1 - 控制指令需要确认
            self.client.publish(
                self.topic,
                json.dumps(self.data),
                qos=1
            )
            print(f"[Lighting] Published (QoS 1): {self.data}")
        except Exception as e:
            print(f"[Lighting] Publish error: {e}")

# 保持LightingSubscriber类完全不变
class LightingSubscriber:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/lighting"
        self.client.message_callback_add(self.topic, self.on_message)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Lighting] Received: {data}")
        except json.JSONDecodeError:
            print(f"[Lighting] Invalid data received")
