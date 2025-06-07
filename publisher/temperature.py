import paho.mqtt.client as mqtt
import json
import random
import time
import numpy as np
import pytz
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
            "anomaly": False  # 新增异常标记字段
        }
        self.temperature_threshold = 25.0

        # 初始化机器学习模型
        self.scaler = StandardScaler()
        self.anomaly_detector = IsolationForest(n_estimators=100, contamination=0.05)

        # 模拟历史数据用于训练
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

        # 昼夜周期变化
        params = self.seasonal_params[self.current_season]
        daily_variation = params['amplitude'] * np.sin(2 * np.pi * hour / 24 + params['phase'])

        # 随机波动
        random_fluctuation = np.random.normal(0, 0.5)

        # 设备发热影响 (下午2-6点)
        device_heat = 1.5 if 14 <= hour < 18 else 0

        # 天气影响 (20%概率出现异常天气)
        weather_effect = 0
        if np.random.random() < 0.2:
            weather_type = np.random.choice(['sunny', 'rainy', 'cloudy', 'windy'])
            weather_effects = {'sunny': 2.0, 'rainy': -3.0, 'cloudy': -1.5, 'windy': -2.5}
            weather_effect = weather_effects[weather_type]

        temp = params['base'] + daily_variation + random_fluctuation + device_heat + weather_effect
        return round(temp, 1)

    def publish(self):
        """合并后的发布方法，包含温度模拟、预测和异常检测"""
        # 生成新温度数据
        real_temp = self._simulate_real_temperature()
        predicted_temp = self.predict_next_temperature(real_temp)

        # 更新数据字典
        self.data = {
            "temperature": predicted_temp,
            "comfort_level": "optimal" if predicted_temp < self.temperature_threshold else "high",
            "anomaly": bool(self.detect_anomaly(predicted_temp))
        }

        try:
            # QoS 1 - 至少交付一次（确保温度数据不丢失）
            self.client.publish(
                self.topic,
                json.dumps(self.data),
                qos=1,
                retain=True  # 保留最后一条消息给新订阅者
            )
            print(f"[Temperature] Published (QoS 1): {self.data}")

            # 异常和高温警告
            if self.data["anomaly"]:
                alert = f"ANOMALY DETECTED! Temperature: {predicted_temp:.1f}°C"
                print(alert)
            elif predicted_temp > self.temperature_threshold:
                alert = f"High temperature warning! Current: {predicted_temp:.1f}°C"
                print(alert)

            # 根据情况调整发布间隔
            time.sleep(5 if (self.data["anomaly"] or predicted_temp > self.temperature_threshold) else 1)

        except Exception as e:
            print(f"[Temperature] Publish error: {e}")

    def generate_synthetic_data(self):
        """生成模拟温度数据（包含正常和异常点）"""
        np.random.seed(42)
        normal_data = np.random.normal(22, 2, 1000)  # 正常温度数据
        anomaly_data = np.concatenate([
            np.random.uniform(30, 40, 50),  # 高温异常
            np.random.uniform(0, 10, 50)  # 低温异常
        ])
        return np.concatenate([normal_data, anomaly_data])

    def train_models(self):
        """训练异常检测模型"""
        # 数据标准化
        X = self.history_data.reshape(-1, 1)
        X_scaled = self.scaler.fit_transform(X)

        # 标记异常数据（后50个是人工注入的异常）
        y = np.array([1] * 1000 + [-1] * 100)

        # 训练集和测试集划分
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        # 训练模型
        self.anomaly_detector.fit(X_train)

        # 评估模型
        test_scores = self.anomaly_detector.decision_function(X_test)
        print(f"Anomaly detection model trained. Test score range: [{test_scores.min():.2f}, {test_scores.max():.2f}]")

    def detect_anomaly(self, temp):
        """检测温度是否异常"""
        scaled_temp = self.scaler.transform([[temp]])
        score = self.anomaly_detector.decision_function(scaled_temp)
        is_anomaly = score < -0.2  # 阈值可根据实际情况调整
        return is_anomaly[0]

    def predict_next_temperature(self, current_temp):
        """简单预测下一个温度值（示例用线性预测）"""
        # 实际项目中可以用更复杂的时序模型如ARIMA、LSTM等
        return current_temp + random.uniform(-0.5, 0.5)


class TemperatureSubscriber:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/temperature"
        self.client.message_callback_add(self.topic, self.on_message)

        # 初始化数据分析模型（示例用简单统计）
        self.temp_history = []
        self.avg_window = 10  # 移动平均窗口大小

    def calculate_moving_average(self):
        """计算温度移动平均值"""
        if len(self.temp_history) >= self.avg_window:
            return sum(self.temp_history[-self.avg_window:]) / self.avg_window
        return None

    def analyze_trend(self):
        """简单趋势分析（示例）"""
        if len(self.temp_history) < 3:
            return "insufficient data"

        recent = self.temp_history[-3:]
        if recent[-1] > recent[0] + 0.5:
            return "rising"
        elif recent[-1] < recent[0] - 0.5:
            return "falling"
        return "stable"

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            temp = data["temperature"]
            self.temp_history.append(temp)

            # 执行数据分析
            moving_avg = self.calculate_moving_average()
            trend = self.analyze_trend()

            print(f"[Temperature] Received: {data} | "
                  f"Moving avg: {moving_avg:.1f}°C | "
                  f"Trend: {trend}")

            # 如果检测到异常，可以触发额外操作
            if data.get("anomaly", False):
                print("[ALERT] Temperature anomaly detected!")

        except json.JSONDecodeError:
            print(f"[Temperature] Invalid data received")
        except Exception as e:
            print(f"[Temperature] Processing error: {e}")
