import paho.mqtt.client as mqtt
import json
import random
import sqlite3


class SecurityPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/security/status"
        self.data = {
            "lock_status": "locked",
            "noise_reduction": "enabled"
        }

    def publish(self):
        self.data["lock_status"] = random.choice(["locked", "unlocked"])
        self.data["noise_reduction"] = random.choice(["enabled", "disabled"])

        try:
            self.client.publish(self.topic, json.dumps(self.data))
            print(f"[Security] Published: {self.data}")
        except Exception as e:
            print(f"[Security] Publish error: {e}")


class SecuritySubscriber:
    def __init__(self, client):
        self.client = client
        self.topic = "home/security/status"
        self.client.message_callback_add(self.topic, self.on_message)
        self.setup_db()

    def setup_db(self):
        self.conn = sqlite3.connect('smart_home.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS security_status (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lock_status TEXT,
                            noise_reduction TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        self.conn.commit()

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Security] Received: {data}")

            self.cursor.execute("INSERT INTO security_status (lock_status, noise_reduction) VALUES (?, ?)",
                                (data['lock_status'], data['noise_reduction']))
            self.conn.commit()
        except json.JSONDecodeError:
            print(f"[Security] Invalid data received")
        except Exception as e:
            print(f"[Security] Database error: {e}")