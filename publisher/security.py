import paho.mqtt.client as mqtt
import json
import random
import sqlite3
import numpy as np
import threading
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from datetime import datetime, timedelta


class SecurityPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/security/status"
        self.data = {
            "lock_status": "locked",
            "noise_reduction": "enabled",
            "time_of_day": self._get_time_of_day()
        }

        # 初始化机器学习模型
        self.lock_model = RandomForestClassifier()
        self.noise_model = RandomForestClassifier()
        self._train_models()
        self.room_type = "living_room"  # 可配置为 bedroom/kitchen等
        self.occupancy = False
        self.last_motion_time = time.time()

    def _simulate_real_lighting(self):
        now = datetime.now()
        hour = now.hour + now.minute/60

        # 基础光照 (考虑昼夜变化)
        if 6 <= hour < 18:  # 白天
            base_light = 80 + 40 * np.sin(np.pi*(hour-12)/12)
        else:  # 夜晚
            base_light = 10 + 5 * np.sin(np.pi*(hour-24)/12)

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

        brightness = base_light + random_effect
        if self.occupancy:
            brightness += motion_effect

        brightness += room_adjustments[self.room_type]
        return np.clip(brightness, 0, 100)

    def publish(self):
        # 使用现实模拟数据
        self.data["brightness"] = int(self._simulate_real_lighting())

        # 智能相机模式 (有人且亮度<30时切到night-vision)
        if self.occupancy and self.data["brightness"] < 30:
            self.data["camera_mode"] = "night-vision"
        else:
            self.data["camera_mode"] = "auto"


    def _get_time_of_day(self):
        """获取当前时间段（早晨/白天/晚上/深夜）"""
        hour = datetime.now().hour
        if 5 <= hour < 9:
            return "morning"
        elif 9 <= hour < 18:
            return "daytime"
        elif 18 <= hour < 23:
            return "evening"
        else:
            return "night"

    def _train_models(self):
        """训练门锁和噪音抑制的预测模型"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()

        # 获取历史数据（假设已有数据）
        cursor.execute('''SELECT lock_status, noise_reduction, 
                          strftime('%H', timestamp) as hour 
                          FROM security_status''')
        records = cursor.fetchall()
        conn.close()

        if len(records) < 50:  # 数据不足时使用默认值
            print("[Security] Not enough historical data for training")
            return

        # 准备特征（时间）和标签
        X = np.array([[int(row[2])] for row in records])  # 使用小时作为特征
        y_lock = np.array([1 if row[0] == "unlocked" else 0 for row in records])
        y_noise = np.array([1 if row[1] == "enabled" else 0 for row in records])

        # 训练模型
        X_train, X_test, y_lock_train, y_lock_test = train_test_split(
            X, y_lock, test_size=0.2, random_state=42)
        self.lock_model.fit(X_train, y_lock_train)
        lock_pred = self.lock_model.predict(X_test)
        print(f"[Security] Lock model accuracy: {accuracy_score(y_lock_test, lock_pred):.2f}")

        X_train, X_test, y_noise_train, y_noise_test = train_test_split(
            X, y_noise, test_size=0.2, random_state=42)
        self.noise_model.fit(X_train, y_noise_train)
        noise_pred = self.noise_model.predict(X_test)
        print(f"[Security] Noise model accuracy: {accuracy_score(y_noise_test, noise_pred):.2f}")

    def _predict_security_settings(self):
        """使用机器学习模型预测安全设置"""
        current_hour = datetime.now().hour

        # 预测门锁状态
        lock_prob = self.lock_model.predict_proba([[current_hour]])[0]
        unlock_prob = lock_prob[1] if len(lock_prob) > 1 else 0.3  # 默认概率

        # 预测噪音抑制
        noise_prob = self.noise_model.predict_proba([[current_hour]])[0]
        enable_prob = noise_prob[1] if len(noise_prob) > 1 else 0.7  # 默认概率

        # 根据概率随机生成状态（加入随机性模拟真实场景）
        self.data["lock_status"] = "unlocked" if random.random() < unlock_prob else "locked"
        self.data["noise_reduction"] = "enabled" if random.random() < enable_prob else "disabled"
        self.data["time_of_day"] = self._get_time_of_day()
        self.data["prediction_confidence"] = {
            "lock": float(unlock_prob),
            "noise": float(enable_prob)
        }

    def publish(self):
        # 使用机器学习模型预测状态（替代完全随机）
        self._predict_security_settings()

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

        # 初始化分析功能
        self._setup_analysis()

    def setup_db(self):
        self.conn = sqlite3.connect('smart_home.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS security_status (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lock_status TEXT,
                            noise_reduction TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        self.conn.commit()

    def _setup_analysis(self):
        """设置定期分析安全模式的功能"""
        self.analysis_timer = None
        self._schedule_next_analysis()

    def _schedule_next_analysis(self):
        """安排下一次分析任务（每6小时一次）"""
        if self.analysis_timer is not None:
            self.analysis_timer.cancel()

        self.analysis_timer = threading.Timer(6 * 3600, self._analyze_patterns)
        self.analysis_timer.start()

    def _analyze_patterns(self):
        """分析历史数据中的安全模式"""
        try:
            # 获取过去7天的数据
            cutoff = datetime.now() - timedelta(days=7)
            self.cursor.execute('''SELECT lock_status, noise_reduction, 
                                  strftime('%H', timestamp) as hour 
                                  FROM security_status 
                                  WHERE timestamp > ?''', (cutoff,))
            records = self.cursor.fetchall()

            if len(records) > 20:
                # 分析最常见的模式组合
                from collections import Counter
                patterns = Counter((r[0], r[1], int(r[2]) // 6) for r in records)  # 按4小时分段
                common_pattern = patterns.most_common(1)[0][0]
                print(f"[Security] Most common pattern: "
                      f"Lock={common_pattern[0]}, Noise={common_pattern[1]}, "
                      f"Time={common_pattern[2] * 6}-{(common_pattern[2] + 1) * 6}h")

            # 重新安排下一次分析
            self._schedule_next_analysis()

        except Exception as e:
            print(f"[Security] Pattern analysis error: {e}")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Security] Received: {data}")

            # 存储到数据库
            self.cursor.execute("INSERT INTO security_status (lock_status, noise_reduction) VALUES (?, ?)",
                                (data['lock_status'], data['noise_reduction']))
            self.conn.commit()

            # 检查异常模式（可选）
            self._check_anomalies(data)

        except json.JSONDecodeError:
            print(f"[Security] Invalid data received")
        except Exception as e:
            print(f"[Security] Database error: {e}")

    def _check_anomalies(self, data):
        """检查异常安全状态（如深夜解锁）"""
        hour = datetime.now().hour
        if data['lock_status'] == "unlocked" and (hour < 6 or hour > 23):
            print(f"[Security] Warning: Unusual unlock detected at night ({hour}:00)")

        if data['noise_reduction'] == "disabled" and (hour > 22 or hour < 8):
            print(f"[Security] Warning: Noise reduction disabled during quiet hours")

    def __del__(self):
        """清理资源"""
        if self.analysis_timer is not None:
            self.analysis_timer.cancel()
        self.conn.close()
    def __del__(self):
        """清理资源"""
        if self.analysis_timer is not None:
            self.analysis_timer.cancel()
        self.conn.close()
