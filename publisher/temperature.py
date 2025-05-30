import paho.mqtt.client as mqtt
import json
import random
import time


class TemperaturePublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/temperature"
        self.data = {
            "temperature": 22.0,
            "comfort_level": "optimal"
        }
        self.temperature_threshold = 25.0

    def publish(self):
        self.data["temperature"] += random.uniform(-0.1, 0.1)
        self.data["comfort_level"] = "optimal" if self.data["temperature"] < self.temperature_threshold else "high"

        try:
            self.client.publish(self.topic, json.dumps(self.data))
            print(f"[Temperature] Published: {self.data}")

            if self.data["temperature"] > self.temperature_threshold:
                alert = f"Temperature warning! Current: {self.data['temperature']}°C (Threshold: {self.temperature_threshold}°C)"
                print(alert)
                time.sleep(5)
        except Exception as e:
            print(f"[Temperature] Publish error: {e}")


class TemperatureSubscriber:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/temperature"
        self.client.message_callback_add(self.topic, self.on_message)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Temperature] Received: {data}")
        except json.JSONDecodeError:
            print(f"[Temperature] Invalid data received")