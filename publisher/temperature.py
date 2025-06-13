import paho.mqtt.client as mqtt
import json
import random
import time
import numpy as np
import pytz
import os
import requests
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from datetime import datetime, timedelta

class TemperaturePublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/temperature"
        self.data = {
            "temperature": 22.0,
            "comfort_level": "optimal",
            "anomaly": False
        }
        self.temperature_threshold = 25.0

        self.scaler = StandardScaler()
        self.anomaly_detector = IsolationForest(n_estimators=100, contamination=0.05)

        self.history_data = self.generate_synthetic_data()
        self.train_models()

        self.seasonal_params = {
            'winter': {'base': 18.0, 'amplitude': 3.0, 'phase': 0},
            'spring': {'base': 22.0, 'amplitude': 5.0, 'phase': np.pi / 2},
            'summer': {'base': 28.0, 'amplitude': 7.0, 'phase': np.pi},
            'autumn': {'base': 20.0, 'amplitude': 4.0, 'phase': 3 * np.pi / 2}
        }
        self.current_season = self._get_current_season()
        self.timezone = pytz.timezone('Asia/Shanghai')

        self.api_key = os.getenv("OWM_API_KEY", "your_api_key_here")
        self.city = "Shanghai"
        self.external_temp = 22.0

    def _update_weather(self):
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.api_key}&units=metric"
            response = requests.get(url, timeout=3)
            weather_data = response.json()
            if "main" in weather_data:
                self.external_temp = float(weather_data["main"]["temp"])
        except Exception as e:
            print(f"[Weather API] Error: {e}")

    def _get_current_season(self):
        month = datetime.now().month
        if month in [12, 1, 2]:
            return 'winter'
        elif month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8]:
            return 'summer'
        else:
            return 'autumn'

    def _simulate_real_temperature(self):
        now = datetime.now(self.timezone)
        hour = now.hour + now.minute / 60

        self._update_weather()

        params = self.seasonal_params[self.current_season]
        daily_variation = params['amplitude'] * np.sin(2 * np.pi * hour / 24 + params['phase'])
        random_fluctuation = np.random.normal(0, 0.5)
        device_heat = 1.5 if 14 <= hour < 18 else 0

        # 替换原有20%概率模拟天气为实际天气温度
        temp = (params['base'] + daily_variation + random_fluctuation + device_heat + self.external_temp) / 2
        return round(temp, 1)

    def publish(self):
        real_temp = self._simulate_real_temperature()
        self.data["temperature"] = real_temp

        if real_temp < 18:
            self.data["comfort_level"] = "cold"
        elif 18 <= real_temp < 24:
            self.data["comfort_level"] = "optimal"
        elif 24 <= real_temp < 28:
            self.data["comfort_level"] = "warm"
        else:
            self.data["comfort_level"] = "hot"

        try:
            self.client.publish(
                self.topic,
                json.dumps(self.data),
                qos=1,
                retain=True
            )
            print(f"[Temperature] Published (QoS 1): {self.data}")
        except Exception as e:
            print(f"[Temperature] Publish error: {e}")

    def generate_synthetic_data(self):
        np.random.seed(42)
        normal_data = np.random.normal(22, 2, 1000)
        anomaly_data = np.concatenate([
            np.random.uniform(30, 40, 50),
            np.random.uniform(0, 10, 50)
        ])
        return np.concatenate([normal_data, anomaly_data])

    def train_models(self):
        X = self.history_data.reshape(-1, 1)
        X_scaled = self.scaler.fit_transform(X)
        y = np.array([1] * 1000 + [-1] * 100)
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42)
        self.anomaly_detector.fit(X_train)
        test_scores = self.anomaly_detector.decision_function(X_test)
        print(f"Anomaly detection model trained. Test score range: [{test_scores.min():.2f}, {test_scores.max():.2f}]")

    def detect_anomaly(self, temp):
        scaled_temp = self.scaler.transform([[temp]])
        score = self.anomaly_detector.decision_function(scaled_temp)
        return score[0] < -0.2

    def predict_next_temperature(self, current_temp):
        return current_temp + random.uniform(-0.5, 0.5)

    def publish(self):
        predicted_temp = self.predict_next_temperature(self.data["temperature"])
        self.data["temperature"] = predicted_temp
        self.data["comfort_level"] = (
            "cold" if predicted_temp < 18 else
            "optimal" if predicted_temp < 24 else
            "warm" if predicted_temp < 28 else "hot"
        )
        self.data["anomaly"] = bool(self.detect_anomaly(predicted_temp))

        try:
            self.client.publish(self.topic, json.dumps(self.data))
            print(f"[Temperature] Published: {self.data}")

            if self.data["anomaly"]:
                alert = f"ANOMALY DETECTED! Temperature: {predicted_temp:.1f}°C"
                print(alert)
            elif predicted_temp > self.temperature_threshold:
                alert = f"High temperature warning! Current: {predicted_temp:.1f}°C"
                print(alert)

            time.sleep(5 if (self.data["anomaly"] or predicted_temp > self.temperature_threshold) else 1)

        except Exception as e:
            print(f"[Temperature] Publish error: {e}")
