def run_subscriber():
    import paho.mqtt.client as mqtt
    import time
    import json
    import sqlite3

    topic = "sensor/temp"
    db_path = "latency_log.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS latency_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sent_time REAL,
        received_time REAL,
        latency REAL
    )''')
    conn.commit()

    def on_connect(client, userdata, flags, rc):
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        received_time = time.time()
        payload = json.loads(msg.payload.decode())
        sent_time = payload["timestamp"]
        latency = received_time - sent_time

        print(f"[RECEIVE] Sent: {sent_time:.6f}, Received: {received_time:.6f}, Latency: {latency*1000:.2f} ms")
        cursor.execute("INSERT INTO latency_log (sent_time, received_time, latency) VALUES (?, ?, ?)",
                       (sent_time, received_time, latency))
        conn.commit()

    client = mqtt.Client()
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("localhost", 8883)
    client.loop_forever()
