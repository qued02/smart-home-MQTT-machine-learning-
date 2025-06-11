import unittest
from unittest.mock import MagicMock, patch, call
import paho.mqtt.client as mqtt
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
import time
import queue
import tkinter as tk
from matplotlib import pyplot as plt

# 导入要测试的类
from publisher.lighting import LightingPublisher, LightingSubscriber
from publisher.security import SecurityPublisher, SecuritySubscriber
from publisher.temperature import TemperaturePublisher, TemperatureSubscriber
from system import SmartHomeSystem
from ui import SmartHomeUI

class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 创建内存数据库用于测试
        cls.conn = sqlite3.connect(':memory:')
        cls.cursor = cls.conn.cursor()
        
        # 创建测试表结构
        cls.create_test_tables()
        
    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        
    @classmethod
    def create_test_tables(cls):
        cls.cursor.execute('''CREATE TABLE temperature (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            temperature REAL,
                            comfort_level TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cls.cursor.execute('''CREATE TABLE lighting (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            brightness INTEGER,
                            camera_mode TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cls.cursor.execute('''CREATE TABLE security_status (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lock_status TEXT,
                            noise_reduction TEXT,
                            motion_detected INTEGER,
                            window_status TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        cls.conn.commit()

class TestLightingPublisher(BaseTest):
    def setUp(self):
        self.mock_client = MagicMock()
        self.publisher = LightingPublisher(self.mock_client)
        
    def test_initial_values(self):
        """测试初始化值是否正确"""
        self.assertEqual(self.publisher.topic, "home/sensor/lighting")
        self.assertEqual(self.publisher.data["brightness"], 80)
        self.assertIn(self.publisher.data["camera_mode"], ["auto", "manual", "off"])
        self.assertEqual(self.publisher.previous_brightness, 80)
        self.assertAlmostEqual(self.publisher.smoothing_factor, 0.3)
        
    def test_simulate_real_lighting_daytime(self):
        """测试白天光照模拟"""
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 12  # 中午12点
            brightness = self.publisher._simulate_real_lighting()
            self.assertGreaterEqual(brightness, 40)
            self.assertLessEqual(brightness, 120)  # 考虑波动
            
    def test_simulate_real_lighting_night(self):
        """测试夜晚光照模拟"""
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 2  # 凌晨2点
            brightness = self.publisher._simulate_real_lighting()
            self.assertGreaterEqual(brightness, 5)
            self.assertLessEqual(brightness, 15)
            
    def test_simulate_with_motion(self):
        """测试有运动时的光照模拟"""
        with patch('numpy.random.random', return_value=0.1):  # 模拟检测到运动
            brightness = self.publisher._simulate_real_lighting()
            self.assertGreaterEqual(brightness, 30)  # 运动至少增加30亮度
            
    def test_publish_qos(self):
        """测试发布时的QoS设置"""
        self.publisher.publish()
        args, kwargs = self.mock_client.publish.call_args
        self.assertEqual(kwargs['qos'], 1)  # 照明控制需要确认
        
    def test_train_model_accuracy(self):
        """测试模型训练后的准确度"""
        self.publisher.train_model()
        self.assertLess(self.publisher.model.score(
            self.publisher.history_data[:, 0].reshape(-1, 1),
            self.publisher.history_data[:, 1]
        ), 1.0)  # 确保不是过拟合
        
    def test_predict_brightness_adjustment(self):
        """测试亮度调整预测"""
        test_light = 50
        predicted = self.publisher.predict_brightness_adjustment(test_light)
        self.assertGreaterEqual(predicted, 0)
        self.assertLessEqual(predicted, 100)

class TestLightingSubscriber(BaseTest):
    def setUp(self):
        self.mock_client = MagicMock()
        self.subscriber = LightingSubscriber(self.mock_client)
        
    def test_message_callback_added(self):
        """测试是否正确添加了消息回调"""
        self.mock_client.message_callback_add.assert_called_once_with(
            "home/sensor/lighting", self.subscriber.on_message)
            
    def test_on_message_valid_data(self):
        """测试处理有效数据"""
        test_data = {"brightness": 75, "camera_mode": "manual"}
        msg = MagicMock()
        msg.topic = "home/sensor/lighting"
        msg.payload = json.dumps(test_data).encode('utf-8')
        
        with patch('builtins.print') as mock_print:
            self.subscriber.on_message(self.mock_client, None, msg)
            mock_print.assert_called_once_with(
                f"[Lighting] Received: {test_data}")
                
    def test_on_message_invalid_json(self):
        """测试处理无效JSON数据"""
        msg = MagicMock()
        msg.payload = b'invalid json data'
        
        with patch('builtins.print') as mock_print:
            self.subscriber.on_message(self.mock_client, None, msg)
            mock_print.assert_called_once_with(
                "[Lighting] Invalid data received")

class TestSecurityPublisher(BaseTest):
    def setUp(self):
        self.mock_client = MagicMock()
        self.publisher = SecurityPublisher(self.mock_client)
        
    def test_initial_security_status(self):
        """测试初始安全状态"""
        self.assertEqual(self.publisher.data["lock_status"], "locked")
        self.assertEqual(self.publisher.data["noise_reduction"], "enabled")
        
    def test_simulate_security_sensors_daytime(self):
        """测试白天安全传感器模拟"""
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 10  # 上午10点
            sensor_data = self.publisher._simulate_security_sensors()
            self.assertIn(sensor_data["window_status"], ["open", "closed"])
            
    def test_simulate_security_sensors_night(self):
        """测试夜晚安全传感器模拟"""
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 1  # 凌晨1点
            with patch('random.random', return_value=0.05):  # 模拟检测到运动
                sensor_data = self.publisher._simulate_security_sensors()
                self.assertTrue(sensor_data["motion_detected"])
                
    def test_publish_qos_and_retain(self):
        """测试发布时的QoS和retain标志"""
        self.publisher.publish()
        args, kwargs = self.mock_client.publish.call_args
        self.assertEqual(kwargs['qos'], 2)  # 安全消息最高优先级
        self.assertTrue(kwargs['retain'])  # 需要保留消息
        
    def test_train_models_with_mock_db(self):
        """测试使用模拟数据库训练模型"""
        # 插入测试数据
        test_data = [
            ("locked", "enabled", 2, 0),  # 深夜锁定
            ("unlocked", "disabled", 10, 1),  # 白天工作日解锁
            ("locked", "enabled", 22, 1)  # 晚上锁定
        ]
        
        for status, noise, hour, weekday in test_data:
            self.cursor.execute(
                "INSERT INTO security_status (lock_status, noise_reduction) "
                "VALUES (?, ?)", (status, noise))
        
        self.conn.commit()
        
        with patch('sqlite3.connect', return_value=self.conn):
            self.publisher._train_models()
            self.assertGreaterEqual(
                self.publisher.model_metrics['lock']['accuracy'], 0.5)
            self.assertGreaterEqual(
                self.publisher.model_metrics['noise']['accuracy'], 0.5)

class TestSecuritySubscriber(BaseTest):
    def setUp(self):
        self.mock_client = MagicMock()
        self.subscriber = SecuritySubscriber(self.mock_client)
        
    def test_db_setup(self):
        """测试数据库是否正确初始化"""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in self.cursor.fetchall()]
        self.assertIn("security_status", tables)
        
    def test_on_message_store_to_db(self):
        """测试消息是否存储到数据库"""
        test_data = {
            "lock_status": "unlocked",
            "noise_reduction": "disabled",
            "motion_detected": True,
            "window_status": "closed"
        }
        
        msg = MagicMock()
        msg.topic = "home/security/status"
        msg.payload = json.dumps(test_data).encode('utf-8')
        
        initial_count = self.cursor.execute(
            "SELECT COUNT(*) FROM security_status").fetchone()[0]
            
        self.subscriber.on_message(self.mock_client, None, msg)
        
        new_count = self.cursor.execute(
            "SELECT COUNT(*) FROM security_status").fetchone()[0]
        self.assertEqual(new_count, initial_count + 1)
        
    def test_analyze_patterns(self):
        """测试安全模式分析功能"""
        # 插入测试数据
        test_data = [
            ("locked", "enabled", 1, "closed", "2023-01-01 02:00:00"),
            ("locked", "enabled", 0, "closed", "2023-01-01 03:00:00"),
            ("unlocked", "disabled", 1, "open", "2023-01-01 12:00:00")
        ]
        
        for status, noise, motion, window, ts in test_data:
            self.cursor.execute(
                "INSERT INTO security_status "
                "(lock_status, noise_reduction, motion_detected, window_status, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (status, noise, motion, window, ts))
        
        self.conn.commit()
        
        with patch('builtins.print') as mock_print:
            self.subscriber._analyze_patterns()
            mock_print.assert_called()
            args, _ = mock_print.call_args
            self.assertIn("Most common pattern", args[0])

class TestTemperaturePublisher(BaseTest):
    def setUp(self):
        self.mock_client = MagicMock()
        self.publisher = TemperaturePublisher(self.mock_client)
        
    def test_seasonal_temperature_variation(self):
        """测试不同季节的温度变化"""
        seasons = {
            'winter': (18.0, 3.0),
            'spring': (22.0, 5.0),
            'summer': (28.0, 7.0),
            'autumn': (20.0, 4.0)
        }
        
        for season, (base, amp) in seasons.items():
            with patch.object(self.publisher, '_get_current_season', return_value=season):
                temp = self.publisher._simulate_real_temperature()
                self.assertGreaterEqual(temp, base - amp)
                self.assertLessEqual(temp, base + amp)
                
    def test_weather_effects(self):
        """测试天气对温度的影响"""
        weather_cases = [
            ('sunny', 2.0),
            ('rainy', -3.0),
            ('cloudy', -1.5),
            ('windy', -2.5)
        ]
        
        for weather, effect in weather_cases:
            with patch('numpy.random.choice', return_value=weather):
                base_temp = self.publisher._simulate_real_temperature()
                with patch('numpy.random.random', return_value=0.1):  # 触发天气效果
                    temp = self.publisher._simulate_real_temperature()
                    self.assertAlmostEqual(temp - base_temp, effect, delta=1.0)
                    
    def test_anomaly_detection(self):
        """测试异常温度检测"""
        # 正常温度范围
        self.assertFalse(self.publisher.detect_anomaly(22))
        
        # 异常高温
        self.assertTrue(self.publisher.detect_anomaly(40))
        
        # 异常低温
        self.assertTrue(self.publisher.detect_anomaly(5))
        
    def test_publish_with_anomaly(self):
        """测试发布异常温度警告"""
        with patch.object(self.publisher, '_simulate_real_temperature', return_value=40):
            with patch('builtins.print') as mock_print:
                self.publisher.publish()
                mock_print.assert_any_call("ANOMALY DETECTED!")

class TestTemperatureSubscriber(BaseTest):
    def setUp(self):
        self.mock_client = MagicMock()
        self.subscriber = TemperatureSubscriber(self.mock_client)
        
    def test_trend_analysis(self):
        """测试温度趋势分析"""
        # 上升趋势
        self.subscriber.temp_history = [20, 21, 22]
        self.assertEqual(self.subscriber.analyze_trend(), "rising")
        
        # 下降趋势
        self.subscriber.temp_history = [22, 21, 20]
        self.assertEqual(self.subscriber.analyze_trend(), "falling")
        
        # 稳定
        self.subscriber.temp_history = [21, 21, 21]
        self.assertEqual(self.subscriber.analyze_trend(), "stable")
        
    def test_moving_average(self):
        """测试移动平均计算"""
        self.subscriber.temp_history = [20, 21, 22, 23, 24]
        self.subscriber.avg_window = 3
        self.assertAlmostEqual(self.subscriber.calculate_moving_average(), 23)
        
    def test_on_message_alert(self):
        """测试处理温度警报"""
        test_data = {"temperature": 40, "comfort_level": "high", "anomaly": True}
        msg = MagicMock()
        msg.topic = "home/sensor/temperature"
        msg.payload = json.dumps(test_data).encode('utf-8')
        
        with patch('builtins.print') as mock_print:
            self.subscriber.on_message(self.mock_client, None, msg)
            mock_print.assert_any_call("[ALERT] Temperature anomaly detected!")

class TestSmartHomeSystem(BaseTest):
    def setUp(self):
        self.system = SmartHomeSystem()
        self.system.client = MagicMock()
        
    def test_database_maintenance(self):
        """测试数据库维护功能"""
        # 插入一些测试数据
        self.cursor.execute(
            "INSERT INTO temperature (temperature, comfort_level, timestamp) "
            "VALUES (22.5, 'optimal', datetime('now', '-31 days'))")
        self.conn.commit()
        
        initial_count = self.cursor.execute(
            "SELECT COUNT(*) FROM temperature").fetchone()[0]
            
        with patch('sqlite3.connect', return_value=self.conn):
            self.system.optimize_database()
            
        remaining_count = self.cursor.execute(
            "SELECT COUNT(*) FROM temperature").fetchone()[0]
        self.assertLess(remaining_count, initial_count)
        
    def test_message_routing(self):
        """测试消息路由到正确的处理器"""
        test_cases = [
            ("home/sensor/temperature", {"temperature": 22.5}, "handle_temperature_data"),
            ("home/sensor/lighting", {"brightness": 80}, "handle_lighting_data"),
            ("home/security/status", {"lock_status": "locked"}, "handle_security_data")
        ]
        
        for topic, data, handler_name in test_cases:
            msg = MagicMock()
            msg.topic = topic
            msg.payload = json.dumps(data).encode('utf-8')
            
            with patch.object(self.system, handler_name) as mock_handler:
                self.system.on_message(self.system.client, None, msg)
                mock_handler.assert_called_once()
                
    def test_publish_timer(self):
        """测试定时发布功能"""
        with patch.object(self.system.temp_pub, 'publish'), \
             patch.object(self.system.light_pub, 'publish'), \
             patch.object(self.system.security_pub, 'publish'):
                 
            self.system.setup_publish_timer()
            self.system.root.after(1000, self.system.root.quit)
            self.system.root.mainloop()
            
            self.system.temp_pub.publish.assert_called()
            self.system.light_pub.publish.assert_called()
            self.system.security_pub.publish.assert_called()

class TestSmartHomeUI(BaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = tk.Tk()
        cls.root.withdraw()  # 隐藏主窗口
        
    def setUp(self):
        self.ui = SmartHomeUI(self.root)
        self.ui.client = MagicMock()
        
    def test_ui_initialization(self):
        """测试UI初始化"""
        self.assertEqual(self.ui.broker, "test.mosquitto.org")
        self.assertEqual(self.ui.port, 8883)
        self.assertIsNotNone(self.ui.notebook)
        self.assertIsNotNone(self.ui.connection_status)
        
    def test_update_temperature_display(self):
        """测试温度显示更新"""
        test_data = {"temperature": 22.5, "comfort_level": "optimal"}
        self.ui.update_temperature_data(test_data)
        self.assertEqual(self.ui.current_data["temperature"], test_data)
        self.assertEqual(self.ui.temp_var.get(), "22.5 °C")
        
    def test_lighting_controls(self):
        """测试照明控制交互"""
        # 模拟滑动亮度控制
        self.ui.on_lighting_change("brightness", 75)
        self.assertEqual(self.ui.current_data["lighting"]["brightness"], 75)
        
        # 模拟选择相机模式
        self.ui.on_lighting_change("camera_mode", "manual")
        self.assertEqual(self.ui.current_data["lighting"]["camera_mode"], "manual")
        
    def test_security_controls(self):
        """测试安全控制交互"""
        # 模拟切换门锁状态
        self.ui.on_security_change("lock_status", "unlocked")
        self.assertEqual(self.ui.current_data["security"]["lock_status"], "unlocked")
        
        # 模拟切换噪音抑制
        self.ui.on_security_change("noise_reduction", "disabled")
        self.assertEqual(self.ui.current_data["security"]["noise_reduction"], "disabled")
        
    def test_notification_system(self):
        """测试通知系统"""
        initial_count = len(self.ui.all_notifications)
        
        # 添加不同级别的通知
        self.ui.add_notification("Info message", "info")
        self.ui.add_notification("Warning message", "warning")
        self.ui.add_notification("Alert message", "alert")
        
        self.assertEqual(len(self.ui.all_notifications), initial_count + 3)
        
        # 测试过滤功能
        self.ui.filter_notifications("warning")
        self.assertIn("Warning message", self.ui.notification_list.get(0))
        
    def test_history_chart_updates(self):
        """测试历史图表更新"""
        # 插入测试数据
        test_data = [
            (22.0, "2023-01-01 12:00:00"),
            (23.5, "2023-01-01 12:30:00"),
            (22.8, "2023-01-01 13:00:00")
        ]
        
        for temp, ts in test_data:
            self.cursor.execute(
                "INSERT INTO temperature (temperature, timestamp) VALUES (?, ?)",
                (temp, ts))
        
        self.conn.commit()
        
        with patch('sqlite3.connect', return_value=self.conn):
            self.ui.data_type.set("temperature")
            self.ui.time_range.set("24小时")
            self.ui.update_history_chart()
            
            # 验证图表已更新
            self.assertIsNotNone(self.ui.history_ax.lines)

class IntegrationTest(BaseTest):
    """端到端集成测试"""
    
    def test_full_lighting_workflow(self):
        """测试完整的照明系统工作流"""
        # 创建MQTT客户端模拟器
        mock_client = MagicMock()
        
        # 初始化发布者和订阅者
        publisher = LightingPublisher(mock_client)
        subscriber = LightingSubscriber(mock_client)
        
        # 模拟发布消息
        test_data = {"brightness": 80, "camera_mode": "auto"}
        publisher.data = test_data
        publisher.publish()
        
        # 验证MQTT发布调用
        args, kwargs = mock_client.publish.call_args
        self.assertEqual(args[0], "home/sensor/lighting")
        self.assertEqual(json.loads(args[1]), test_data)
        self.assertEqual(kwargs['qos'], 1)
        
        # 模拟MQTT消息接收
        msg = MagicMock()
        msg.topic = "home/sensor/lighting"
        msg.payload = json.dumps(test_data).encode('utf-8')
        
        # 验证消息处理
        with patch('builtins.print') as mock_print:
            subscriber.on_message(mock_client, None, msg)
            mock_print.assert_called_once_with(
                f"[Lighting] Received: {test_data}")
                
    def test_temperature_anomaly_workflow(self):
        """测试温度异常检测工作流"""
        mock_client = MagicMock()
        publisher = TemperaturePublisher(mock_client)
        
        # 模拟异常高温
        with patch.object(publisher, '_simulate_real_temperature', return_value=40):
            with patch('builtins.print') as mock_print:
                publisher.publish()
                
                # 验证异常检测
                mock_print.assert_any_call("ANOMALY DETECTED!")
                
                # 验证发布的数据包含异常标记
                args, _ = mock_client.publish.call_args
                published_data = json.loads(args[1])
                self.assertTrue(published_data["anomaly"])
                
    def test_security_alert_workflow(self):
        """测试安全警报工作流"""
        mock_client = MagicMock()
        publisher = SecurityPublisher(mock_client)
        subscriber = SecuritySubscriber(mock_client)
        
        # 设置数据库连接
        subscriber.conn = self.conn
        subscriber.cursor = self.cursor
        
        # 模拟夜间窗户打开且有运动
        test_data = {
            "lock_status": "locked",
            "noise_reduction": "enabled",
            "motion_detected": True,
            "window_status": "open"
        }
        
        # 模拟发布
        publisher.data = test_data
        publisher.publish()
        
        # 模拟接收
        msg = MagicMock()
        msg.topic = "home/security/status"
        msg.payload = json.dumps(test_data).encode('utf-8')
        
        with patch('datetime.datetime') as mock_datetime, \
             patch('builtins.print') as mock_print:
                 
            mock_datetime.now.return_value.hour = 2  # 凌晨2点
            subscriber.on_message(mock_client, None, msg)
            
            # 验证警报打印
            mock_print.assert_any_call(
                "[Security] Alert: Motion detected with open window at night!")
            
            # 验证数据存储
            count = self.cursor.execute(
                "SELECT COUNT(*) FROM security_status").fetchone()[0]
            self.assertEqual(count, 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
