import ssl
import paho.mqtt.client as mqtt
import json
import sqlite3

BROKER = 'test.mosquitto.org'
PORT = 8883
TEMPERATURE_TOPIC = "home/sensor/temperature"
LIGHTING_TOPIC = "home/sensor/lighting"
SECURITY_TOPIC = "home/security/status"


def connect_to_db():
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
                    camera_mode TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS security_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lock_status TEXT,  # 从smart_lock改为lock_status
                    noise_reduction TEXT)''')
    conn.commit()
    return conn, cursor


def insert_data_to_db(cursor, topic, data):
    if topic == TEMPERATURE_TOPIC:
        cursor.execute("INSERT INTO temperature (temperature, comfort_level) VALUES (?, ?)",
                       (data['temperature'], data['comfort_level']))
    elif topic == LIGHTING_TOPIC:
        cursor.execute("INSERT INTO lighting (brightness, camera_mode) VALUES (?, ?)",
                       (data['brightness'], data['camera_mode']))
    elif topic == SECURITY_TOPIC:
        cursor.execute("INSERT INTO security_status (lock_status, noise_reduction) VALUES (?, ?)",
                       (data['lock_status'], data['noise_reduction']))

def on_message(client, userdata, msg):
    topic = msg.topic
    payload_str = msg.payload.decode('utf-8', errors='ignore')

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        print(f"[Subscriber] Invalid data on {topic}: {payload_str}")
        return

    conn, cursor = connect_to_db()

    if topic == TEMPERATURE_TOPIC:
        print(f"[Subscriber] Received temperature data: {payload}")
    elif topic == LIGHTING_TOPIC:
        print(f"[Subscriber] Received lighting data: {payload}")
    elif topic == SECURITY_TOPIC:
        print(f"[Subscriber] Received privacy data: {payload}")

    insert_data_to_db(cursor, topic, payload)
    conn.commit()
    conn.close()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Subscriber] Connected to Broker!")
        # 温度数据 - QoS 1
        client.subscribe(TEMPERATURE_TOPIC, qos=1)
        # 照明数据 - QoS 1
        client.subscribe(LIGHTING_TOPIC, qos=1)
        # 安全数据 - QoS 2
        client.subscribe(SECURITY_TOPIC, qos=2)
        print(f"[Subscriber] Subscribed with QoS levels")
        print(f"[Subscriber] Subscribed to {TEMPERATURE_TOPIC}, {LIGHTING_TOPIC}, {SECURITY_TOPIC}")
    else:
        print(f"[Subscriber] Failed to connect. Return code: {rc}")

# 主函数
def main():
    mqtt_client = mqtt.Client(client_id="SmartHomeSubscriber")
    # 添加TLS配置
    mqtt_client.tls_set(
        ca_certs="mosquitto.org.crt",
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLSv1_2
    )

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    # 使用8883端口
    mqtt_client.connect(BROKER, PORT, 60)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    main()
