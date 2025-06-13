import threading
import time
import json
import datetime
import sqlite3
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta

# 定义主题
SCHEDULER_TOPIC = "home/scheduler"

class SchedulerPublisher:
    """定时任务发布者，负责创建和管理定时任务"""
    
    def __init__(self, mqtt_client=None):
        """初始化定时任务发布者
        
        参数:
            mqtt_client: MQTT客户端实例
        """
        self.mqtt_client = mqtt_client
        self.schedules = {}  # 存储所有定时任务
        self.running = False
        self.scheduler_thread = None
        self.lock = threading.Lock()  # 用于线程安全操作
        
        # 定义主题
        self.topics = {
            "temperature": "home/sensor/temperature",
            "lighting": "home/sensor/lighting",
            "security": "home/security/status"
        }
        
        # 从数据库加载已保存的定时任务
        self.load_schedules()
    
    def load_schedules(self):
        """从数据库加载已保存的定时任务"""
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            # 检查表是否存在，不存在则创建
            cursor.execute('''CREATE TABLE IF NOT EXISTS schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            device_type TEXT,
                            action TEXT,
                            parameters TEXT,
                            schedule_time TEXT,
                            repeat_days TEXT,
                            enabled INTEGER,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # 加载所有启用的定时任务
            cursor.execute("SELECT id, name, device_type, action, parameters, schedule_time, repeat_days FROM schedules WHERE enabled = 1")
            rows = cursor.fetchall()
            
            for row in rows:
                schedule_id, name, device_type, action, parameters, schedule_time, repeat_days = row
                parameters = json.loads(parameters)
                repeat_days = json.loads(repeat_days) if repeat_days else []
                
                self.schedules[schedule_id] = {
                    'name': name,
                    'device_type': device_type,
                    'action': action,
                    'parameters': parameters,
                    'schedule_time': schedule_time,
                    'repeat_days': repeat_days,
                    'enabled': True
                }
                
            conn.close()
            print(f"已加载 {len(self.schedules)} 个定时任务")
            
        except Exception as e:
            print(f"加载定时任务出错: {e}")
            # 确保表存在
            self.create_schedule_table()
    
    def create_schedule_table(self):
        """创建定时任务表"""
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            device_type TEXT,
                            action TEXT,
                            parameters TEXT,
                            schedule_time TEXT,
                            repeat_days TEXT,
                            enabled INTEGER,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            conn.commit()
            conn.close()
            print("创建定时任务表成功")
        except Exception as e:
            print(f"创建定时任务表出错: {e}")
    
    def add_schedule(self, name, device_type, action, parameters, schedule_time, repeat_days=None):
        """添加新的定时任务
        
        参数:
            name: 定时任务名称
            device_type: 设备类型 (temperature, lighting, security)
            action: 执行的动作
            parameters: 动作参数 (字典)
            schedule_time: 执行时间 (HH:MM 格式)
            repeat_days: 重复执行的星期几 (列表，0-6 表示周一到周日)
        """
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            # 将参数转换为JSON字符串
            parameters_json = json.dumps(parameters)
            repeat_days_json = json.dumps(repeat_days) if repeat_days else None
            
            # 插入数据库
            cursor.execute(
                "INSERT INTO schedules (name, device_type, action, parameters, schedule_time, repeat_days, enabled) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, device_type, action, parameters_json, schedule_time, repeat_days_json, 1)
            )
            
            conn.commit()
            schedule_id = cursor.lastrowid
            conn.close()
            
            # 添加到内存中的调度列表
            with self.lock:
                self.schedules[schedule_id] = {
                    'name': name,
                    'device_type': device_type,
                    'action': action,
                    'parameters': parameters,
                    'schedule_time': schedule_time,
                    'repeat_days': repeat_days if repeat_days else [],
                    'enabled': True
                }
            
            # 发布定时任务更新消息
            self.publish_schedule_update("add", schedule_id, self.schedules[schedule_id])
            
            print(f"添加定时任务成功: {name}")
            return schedule_id
            
        except Exception as e:
            print(f"添加定时任务出错: {e}")
            return None
    
    def update_schedule(self, schedule_id, **kwargs):
        """更新定时任务
        
        参数:
            schedule_id: 定时任务ID
            **kwargs: 要更新的字段和值
        """
        if schedule_id not in self.schedules:
            print(f"定时任务不存在: {schedule_id}")
            return False
            
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            # 构建更新SQL
            update_fields = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['parameters', 'repeat_days'] and value is not None:
                    value = json.dumps(value)
                update_fields.append(f"{key} = ?")
                values.append(value)
                
            if not update_fields:
                return False
                
            values.append(schedule_id)
            sql = f"UPDATE schedules SET {', '.join(update_fields)} WHERE id = ?"
            
            cursor.execute(sql, values)
            conn.commit()
            conn.close()
            
            # 更新内存中的调度
            with self.lock:
                for key, value in kwargs.items():
                    self.schedules[schedule_id][key] = value
            
            # 发布定时任务更新消息
            self.publish_schedule_update("update", schedule_id, self.schedules[schedule_id])
                    
            print(f"更新定时任务成功: {schedule_id}")
            return True
            
        except Exception as e:
            print(f"更新定时任务出错: {e}")
            return False
    
    def delete_schedule(self, schedule_id):
        """删除定时任务"""
        if schedule_id not in self.schedules:
            print(f"定时任务不存在: {schedule_id}")
            return False
            
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            conn.close()
            
            # 从内存中删除前保存一份用于发布
            schedule_data = self.schedules[schedule_id].copy()
            
            # 从内存中删除
            with self.lock:
                del self.schedules[schedule_id]
            
            # 发布定时任务更新消息
            self.publish_schedule_update("delete", schedule_id, schedule_data)
                
            print(f"删除定时任务成功: {schedule_id}")
            return True
            
        except Exception as e:
            print(f"删除定时任务出错: {e}")
            return False
    
    def enable_schedule(self, schedule_id, enabled=True):
        """启用或禁用定时任务"""
        return self.update_schedule(schedule_id, enabled=1 if enabled else 0)
    
    def get_all_schedules(self):
        """获取所有定时任务"""
        return self.schedules.copy()
    
    def get_schedule(self, schedule_id):
        """获取指定定时任务"""
        return self.schedules.get(schedule_id)
    
    def start(self):
        """启动定时任务调度器"""
        if self.running:
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        print("定时任务调度器已启动")
    
    def stop(self):
        """停止定时任务调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1.0)
        print("定时任务调度器已停止")
    
    def _scheduler_loop(self):
        """定时任务调度循环"""
        while self.running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_weekday = now.weekday()  # 0-6 表示周一到周日
            
            # 检查所有定时任务
            with self.lock:
                for schedule_id, schedule in self.schedules.items():
                    if not schedule.get('enabled', True):
                        continue
                        
                    # 检查时间是否匹配
                    if schedule['schedule_time'] == current_time:
                        # 检查星期几是否匹配
                        repeat_days = schedule.get('repeat_days', [])
                        if not repeat_days or current_weekday in repeat_days:
                            self._execute_schedule(schedule_id, schedule)
            
            # 每分钟检查一次
            time.sleep(60 - datetime.now().second)
    
    def _execute_schedule(self, schedule_id, schedule):
        """执行定时任务"""
        if not self.mqtt_client:
            print(f"无法执行定时任务 {schedule['name']}: MQTT客户端未配置")
            return
            
        device_type = schedule['device_type']
        action = schedule['action']
        parameters = schedule['parameters']
        
        topic = self.topics.get(device_type)
        if not topic:
            print(f"无法执行定时任务 {schedule['name']}: 未知设备类型 {device_type}")
            return
            
        try:
            # 构建消息
            message = json.dumps(parameters)
            
            # 发布消息
            self.mqtt_client.publish(topic, message, qos=1)
            print(f"执行定时任务: {schedule['name']} - {device_type}/{action} - {parameters}")
            
            # 记录执行日志
            self._log_execution(schedule_id, schedule)
            
        except Exception as e:
            print(f"执行定时任务出错: {e}")
    
    def _log_execution(self, schedule_id, schedule):
        """记录定时任务执行日志"""
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            # 检查表是否存在，不存在则创建
            cursor.execute('''CREATE TABLE IF NOT EXISTS schedule_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            schedule_id INTEGER,
                            name TEXT,
                            device_type TEXT,
                            action TEXT,
                            parameters TEXT,
                            executed_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            
            # 记录日志
            cursor.execute(
                "INSERT INTO schedule_logs (schedule_id, name, device_type, action, parameters) VALUES (?, ?, ?, ?, ?)",
                (schedule_id, schedule['name'], schedule['device_type'], schedule['action'], json.dumps(schedule['parameters']))
            )
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"记录定时任务日志出错: {e}")
    
    def get_execution_logs(self, schedule_id=None, limit=10):
        """获取定时任务执行日志"""
        try:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            if schedule_id:
                cursor.execute(
                    "SELECT * FROM schedule_logs WHERE schedule_id = ? ORDER BY executed_at DESC LIMIT ?",
                    (schedule_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM schedule_logs ORDER BY executed_at DESC LIMIT ?",
                    (limit,)
                )
                
            rows = cursor.fetchall()
            conn.close()
            
            return rows
            
        except Exception as e:
            print(f"获取定时任务日志出错: {e}")
            return []
    
    def publish_schedule_update(self, action, schedule_id, schedule_data):
        """发布定时任务更新消息"""
        if not self.mqtt_client:
            return
            
        message = {
            "action": action,
            "id": schedule_id,
            "data": schedule_data
        }
        
        try:
            self.mqtt_client.publish(SCHEDULER_TOPIC, json.dumps(message), qos=1)
        except Exception as e:
            print(f"发布定时任务更新消息出错: {e}")


class SchedulerSubscriber:
    """定时任务订阅者，负责接收定时任务更新"""
    
    def __init__(self, mqtt_client=None, callback=None):
        """初始化定时任务订阅者
        
        参数:
            mqtt_client: MQTT客户端实例
            callback: 接收到定时任务更新时的回调函数
        """
        self.mqtt_client = mqtt_client
        self.callback = callback
        
        if self.mqtt_client:
            self.mqtt_client.message_callback_add(SCHEDULER_TOPIC, self.on_scheduler_message)
            self.mqtt_client.subscribe(SCHEDULER_TOPIC, qos=1)
    
    def on_scheduler_message(self, client, userdata, msg):
        """处理定时任务消息"""
        try:
            payload = msg.payload.decode()
            data = json.loads(payload)
            
            if self.callback:
                self.callback(data)
                
        except Exception as e:
            print(f"处理定时任务消息出错: {e}") 
