import paho.mqtt.client as mqtt
import json
import numpy as np
import time
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class LightingPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/lighting"
        self.data = {
            "brightness": 80,
            "camera_mode": "auto"
        }

        # 初始化线性回归模型
        self.model = LinearRegression()

        # 假设我们有一些历史数据（环境亮度, 目标亮度调整值）
        # 这些数据可以基于实验得到，或者根据人类舒适度标准来设定
        self.history_data = [
            [20, 100],  # 环境亮度20时，目标亮度调整为100
            [30, 95],   # 环境亮度30时，目标亮度调整为95
            [40, 90],   # 环境亮度40时，目标亮度调整为90
            [50, 85],   # 环境亮度50时，目标亮度调整为85
            [60, 80],   # 环境亮度60时，目标亮度调整为80
            [70, 75],   # 环境亮度70时，目标亮度调整为75
            [80, 70],   # 环境亮度80时，目标亮度调整为70
            [90, 65],   # 环境亮度90时，目标亮度调整为65
        ]

        # 使用训练数据训练模型
        self.train_model()

    def train_model(self):
        # 提取特征和目标值
        X = np.array([data[0] for data in self.history_data]).reshape(-1, 1)  # 环境亮度作为特征
        y = np.array([data[1] for data in self.history_data])  # 目标亮度作为输出

        # 将数据分割为训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 训练回归模型
        self.model.fit(X_train, y_train)

        # 测试模型的性能
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f"模型的均方误差 (MSE): {mse}")

    def predict_brightness_adjustment(self, ambient_light):
        # 使用训练好的模型来预测调整后的亮度
        return self.model.predict([[ambient_light]])[0]

    def publish(self):
        # 随机模拟环境亮度
        ambient_light = np.random.randint(10, 100)  # 随机环境亮度

        # 使用训练好的模型预测需要调整的亮度
        adjusted_brightness = self.predict_brightness_adjustment(ambient_light)

        # 随机选择相机模式
        self.data["brightness"] = adjusted_brightness
        self.data["camera_mode"] = np.random.choice(["auto", "manual", "off"])

        try:
            self.client.publish(self.topic, json.dumps(self.data))
            print(f"[Lighting] Published: {self.data}")
        except Exception as e:
            print(f"[Lighting] Publish error: {e}")

        time.sleep(10)


class LightingSubscriber:
    def __init__(self, client):
        self.client = client
        self.topic = "home/sensor/lighting"
        self.client.message_callback_add(self.topic, self.on_message)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            print(f"[Lighting] Received: {data}")
        except json.JSONDecodeError:
            print(f"[Lighting] Invalid data received")