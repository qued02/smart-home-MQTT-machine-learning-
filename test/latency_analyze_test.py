def run_latency_analysis():
    import sqlite3
    import numpy as np

    conn = sqlite3.connect("latency_log.db")
    cursor = conn.cursor()

    cursor.execute("SELECT latency FROM latency_log")
    latencies = [row[0] * 1000 for row in cursor.fetchall()]

    if latencies:
        print(f"Samples: {len(latencies)}")
        print(f"Average Latency: {np.mean(latencies):.2f} ms")
        print(f"Max Latency: {np.max(latencies):.2f} ms")
        print(f"Min Latency: {np.min(latencies):.2f} ms")
        print(f"Standard Deviation: {np.std(latencies):.2f} ms")
    else:
        print("No data recorded.")

