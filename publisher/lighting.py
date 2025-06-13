import paho.mqtt.client as mqtt
import json
import random
import numpy as np
import time
import os
import requests
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from datetime import datetime
from sklearn.preprocessing import StandardScaler, PolynomialFeatures

class LightingPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/lighting"
        self.data = {
            "brightness": 80,
            "camera_mode": "auto"
        }

        self.poly = PolynomialFeatures(degree=2)
        self.scaler = StandardScaler()
        self.model = LinearRegression()
        self.train_model()

        self.room_type = "living_room"
        self.occupancy = False
        self.last_motion_time = time.time()

        self.api_key = os.getenv("OWM_API_KEY", "your_api_key_here")
        self.city = "Shanghai"
        self.weather_condition = "clear"

    def _update_weather(self):
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.api_key}"
            response = requests.get(url, timeout=3)
            weather_data = response.json()
            if "weather" in weather_data:
                self.weather_condition = weather_data["weather"][0]["main"].lower()
        except Exception as e:
            print(f"[Weather API] Error: {e}")

    def _simulate_real_lighting(self):
        now = datetime.now()
        hour = now.hour + now.minute / 60
        self._update_weather()

        if 6 <= hour < 18:
            base_light = 80 + 40 * np.sin(np.pi * (hour - 12) / 12)
        else:
            base_light = 10 + 5 * np.sin(np.pi * (hour - 24) / 12)

        weather_effects = {
            'clear': +10,
            'clouds': -5,
            'rain': -15,
            'thunderstorm': -20,
            'snow': -10
        }
        weather_effect = weather_effects.get(self.weather_condition, 0)

        behavior_effect = 0
        if 6 <= hour <= 8:
            behavior_effect += 20
        if 20 <= hour <= 23 and not self.occupancy:
            behavior_effect -= 15

        motion_effect = 0
        if np.random.random() < 0.3:
            self.occupancy = True
            self.last_motion_time = time.time()
            motion_effect = 30 + np.random.randint(0, 20)
        elif time.time() - self.last_motion_time > 300:
            self.occupancy = False

        room_adjustments = {
            'living_room': 5,
            'bedroom': -10,
            'kitchen': 15,
            'bathroom': 0
        }

        random_effect = np.random.randint(-5, 5)
        brightness = base_light + random_effect + motion_effect + behavior_effect + weather_effect
        brightness += room_adjustments.get(self.room_type, 0)
        # 返回小时数和模拟的亮度值（可选）
        return hour, np.clip(brightness, 0, 100)

    def train_model(self):
        hours = np.random.randint(0, 24, 1000).reshape(-1, 1)
        brightness = np.clip(80 + 30 * np.sin(np.pi * (hours.flatten() - 12) / 12) + np.random.normal(0, 5, 1000), 0, 100)
        
        X_poly = self.poly.fit_transform(hours)
        X_scaled = self.scaler.fit_transform(X_poly)

        X_train, X_test, y_train, y_test = train_test_split(X_scaled, brightness, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        print(f"[Model] Lighting MSE: {mean_squared_error(y_test, y_pred):.2f}")

    def predict_brightness_adjustment(self, hour):
        X = np.array([[hour]])
        X_poly = self.poly.transform(X)
        X_scaled = self.scaler.transform(X_poly)
        pred = self.model.predict(X_scaled)[0]
        return int(np.clip(pred, 0, 100))

    def publish(self):
        current_hour, simulated_brightness = self._simulate_real_lighting()
        # 这里用小时数预测亮度调整
        self.data["brightness"] = self.predict_brightness_adjustment(current_hour)
        self.data["camera_mode"] = random.choice(["auto", "manual", "off"])
        try:
            self.client.publish(self.topic, json.dumps(self.data), qos=1)
            print(f"[Lighting] Published(QoS 1): {self.data}")
        except Exception as e:
            print(f"[Lighting] Publish error: {e}")

class LightingSubscriber:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/lighting"
        self.client.message_callback_add(self.topic, self.on_message)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Lighting] Received: {data}")
        except Exception as e:
            print(f"[Lighting] Error: {e}")
