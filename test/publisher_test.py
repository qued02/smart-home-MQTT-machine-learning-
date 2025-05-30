def run_publisher():
    import paho.mqtt.client as mqtt
    import time
    import json

    broker = "localhost"
    port = 8883
    topic = "sensor/temp"

    client = mqtt.Client()
    client.tls_set()
    client.connect(broker, port)

    for i in range(100):
        timestamp = time.time()
        data = {
            "value": 25 + i % 5,
            "timestamp": timestamp
        }
        client.publish(topic, json.dumps(data))
        print(f"[PUBLISH] {data}")
        time.sleep(0.5)

