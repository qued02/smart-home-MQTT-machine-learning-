def run_stress_test():
    from multiprocessing import Process
    import paho.mqtt.client as mqtt
    import time
    import json

    def publish_worker(sensor_id, count=50):
        client = mqtt.Client()
        client.tls_set()
        client.connect("localhost", 8883)
        topic = "sensor/temp"

        for i in range(count):
            payload = {
                "sensor_id": sensor_id,
                "value": 20 + (i % 10),
                "timestamp": time.time()
            }
            client.publish(topic, json.dumps(payload))
            print(f"[Worker {sensor_id}] Sent {payload}")
            time.sleep(0.1)

    workers = []
    for i in range(5):
        p = Process(target=publish_worker, args=(i,))
        p.start()
        workers.append(p)

    for p in workers:
        p.join()
