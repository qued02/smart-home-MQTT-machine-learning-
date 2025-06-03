import paho.mqtt.client as mqtt
import json
import random
import sqlite3
import numpy as np
import threading
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from datetime import datetime, timedelta


class SecurityPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/security/status"
        self.data = {
            "lock_status": "locked",
            "noise_reduction": "enabled",
            "time_of_day": self._get_time_of_day(),
            "motion_detected": False,
            "window_status": "closed"
        }

        # 初始化机器学习模型
        self.lock_model = RandomForestClassifier()
        self.noise_model = RandomForestClassifier()
        self._train_models()
        self.room_type = "living_room"  # 可配置为 bedroom/kitchen等
        self.last_motion_time = time.time()

    def _simulate_security_sensors(self):
        """模拟安全传感器数据"""
        now = datetime.now()
        hour = now.hour + now.minute / 60

        # 运动检测概率 (夜间更高)
        motion_prob = 0.1  # 基础概率
        if hour < 6 or hour > 22:  # 夜间
            motion_prob = 0.3

        # 随机运动事件
        motion_detected = random.random() < motion_prob
        if motion_detected:
            self.last_motion_time = time.time()

        # 窗户状态 (基于时间和运动)
        window_open = False
        if 8 <= hour <= 20 and motion_detected:  # 白天且有运动
            window_open = random.random() < 0.2

        return {
            "motion_detected": motion_detected,
            "window_status": "open" if window_open else "closed"
        }

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
        conn = None
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()

            # 检查是否有足够数据，否则生成模拟数据
            cursor.execute("SELECT COUNT(*) FROM security_status")
            count = cursor.fetchone()[0]

            if count < 50:
                print("[Security] Generating synthetic training data")
                # 使用更真实的模拟数据模式
                simulated_data = []
                for _ in range(100):
                    hour = random.randint(0, 23)
                    # 更复杂的逻辑规则
                    is_weekday = random.random() < 0.7  # 70%概率是工作日
                    lock_status = "unlocked" if (8 <= hour <= 20 and is_weekday) else "locked"
                    noise_status = "enabled" if (hour >= 22 or hour <= 7) else "disabled"
                    simulated_data.append((lock_status, noise_status, f"{hour:02d}:00:00"))

                # 批量插入提高效率
                cursor.executemany(
                    "INSERT INTO security_status (lock_status, noise_reduction, timestamp) VALUES (?, ?, datetime('now', ? || ' hours'))",
                    [(d[0], d[1], f"-{random.randint(1, 30)}") for d in simulated_data]
                )
                conn.commit()

            # 获取历史数据 - 添加更多特征
            cursor.execute('''SELECT 
                              lock_status, 
                              noise_reduction, 
                              strftime('%H', timestamp) as hour,
                              strftime('%w', timestamp) as weekday  # 0-6, 0是周日
                              FROM security_status''')
            records = cursor.fetchall()

            if not records:
                raise ValueError("No training data available")

            # 准备特征和标签 - 添加更多特征
            X = np.array([
                [int(row[2]), int(row[3])]  # 小时 + 星期几
                for row in records
            ])

            y_lock = np.array([1 if row[0] == "unlocked" else 0 for row in records])
            y_noise = np.array([1 if row[1] == "enabled" else 0 for row in records])

            # 使用不同的随机状态分割数据集
            X_train_lock, X_test_lock, y_train_lock, y_test_lock = train_test_split(
                X, y_lock, test_size=0.2, random_state=42)

            X_train_noise, X_test_noise, y_train_noise, y_test_noise = train_test_split(
                X, y_noise, test_size=0.2, random_state=24)  # 不同的随机种子

            # 训练和评估门锁模型
            self.lock_model.fit(X_train_lock, y_train_lock)
            lock_pred = self.lock_model.predict(X_test_lock)
            lock_acc = accuracy_score(y_test_lock, lock_pred)
            lock_report = classification_report(y_test_lock, lock_pred, target_names=["locked", "unlocked"])
            print(f"[Security] Lock model accuracy: {lock_acc:.2f}")
            print("Classification Report:\n", lock_report)

            # 训练和评估噪音抑制模型
            self.noise_model.fit(X_train_noise, y_train_noise)
            noise_pred = self.noise_model.predict(X_test_noise)
            noise_acc = accuracy_score(y_test_noise, noise_pred)
            noise_report = classification_report(y_test_noise, noise_pred, target_names=["disabled", "enabled"])
            print(f"[Security] Noise model accuracy: {noise_acc:.2f}")
            print("Classification Report:\n", noise_report)

            # 保存模型性能指标供后续使用
            self.model_metrics = {
                'lock': {'accuracy': lock_acc, 'report': lock_report},
                'noise': {'accuracy': noise_acc, 'report': noise_report}
            }

        except Exception as e:
            print(f"[Security] Error in model training: {str(e)}")
            # 可以考虑回退到简单规则
            self.fallback_to_rules = True
        finally:
            if conn:
                conn.close()

    def _predict_security_settings(self):
        """使用机器学习模型预测安全设置"""
        if not hasattr(self, 'lock_model') or not hasattr(self, 'noise_model'):
            # Default behavior when models aren't trained
            self.data["lock_status"] = "locked" if datetime.now().hour > 22 or datetime.now().hour < 6 else "unlocked"
            self.data["noise_reduction"] = "enabled"
            return

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

        # 更新安全传感器数据
        sensor_data = self._simulate_security_sensors()
        self.data.update(sensor_data)

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
                            motion_detected INTEGER,
                            window_status TEXT,
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
            self.cursor.execute('''SELECT lock_status, noise_reduction, motion_detected, window_status,
                                  strftime('%H', timestamp) as hour 
                                  FROM security_status 
                                  WHERE timestamp > ?''', (cutoff,))
            records = self.cursor.fetchall()

            if len(records) > 20:
                # 分析最常见的模式组合
                from collections import Counter
                patterns = Counter((r[0], r[1], r[2], r[3], int(r[4]) // 6) for r in records)  # 按4小时分段
                common_pattern = patterns.most_common(1)[0][0]
                print(f"[Security] Most common pattern: "
                      f"Lock={common_pattern[0]}, Noise={common_pattern[1]}, "
                      f"Motion={common_pattern[2]}, Window={common_pattern[3]}, "
                      f"Time={common_pattern[4] * 6}-{(common_pattern[4] + 1) * 6}h")

            # 重新安排下一次分析
            self._schedule_next_analysis()

        except Exception as e:
            print(f"[Security] Pattern analysis error: {e}")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Security] Received: {data}")

            # 存储到数据库
            self.cursor.execute("""INSERT INTO security_status 
                                (lock_status, noise_reduction, motion_detected, window_status) 
                                VALUES (?, ?, ?, ?)""",
                                (data['lock_status'],
                                 data['noise_reduction'],
                                 int(data['motion_detected']),
                                 data.get('window_status', 'closed')))
            self.conn.commit()

            # 检查异常模式（可选）
            self._check_anomalies(data)

        except json.JSONDecodeError:
            print(f"[Security] Invalid data received")
        except Exception as e:
            print(f"[Security] Database error: {e}")

    def _check_anomalies(self, data):
        """检查异常安全状态"""
        hour = datetime.now().hour

        # 深夜解锁
        if data['lock_status'] == "unlocked" and (hour < 6 or hour > 23):
            print(f"[Security] Warning: Unusual unlock detected at night ({hour}:00)")

        # 安静时间关闭噪音抑制
        if data['noise_reduction'] == "disabled" and (hour > 22 or hour < 8):
            print(f"[Security] Warning: Noise reduction disabled during quiet hours")

        # 夜间检测到运动且窗户打开
        if data['motion_detected'] and data.get('window_status') == "open" and (hour < 6 or hour > 22):
            print(f"[Security] Alert: Motion detected with open window at night!")

    def __del__(self):
        """清理资源"""
        if self.analysis_timer is not None:
            self.analysis_timer.cancel()
        self.conn.close()
