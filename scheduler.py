import paho.mqtt.client as mqtt
import json
import time
import threading
import sqlite3
from datetime import datetime, timedelta
import schedule

class SchedulerPublisher:
    def __init__(self, client):
        self.client = client
        self.topic = "home/scheduler/tasks"
        self.setup_db()
        self.tasks = {}  # 存储所有定时任务
        self.load_tasks_from_db()
        self.scheduler_thread = None
        self.running = False
        
    def setup_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS scheduled_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        device_type TEXT,
                        action TEXT,
                        value TEXT,
                        schedule_type TEXT,
                        schedule_time TEXT,
                        is_active INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        
    def load_tasks_from_db(self):
        """从数据库加载所有定时任务"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, device_type, action, value, schedule_type, schedule_time, is_active FROM scheduled_tasks")
        tasks = cursor.fetchall()
        conn.close()
        
        for task in tasks:
            task_id, name, device_type, action, value, schedule_type, schedule_time, is_active = task
            if is_active:
                self.add_task(task_id, name, device_type, action, value, schedule_type, schedule_time)
                
    def add_task(self, task_id, name, device_type, action, value, schedule_type, schedule_time):
        """添加一个定时任务到调度器"""
        task_data = {
            "id": task_id,
            "name": name,
            "device_type": device_type,
            "action": action,
            "value": value
        }
        
        # 根据不同的调度类型设置任务
        if schedule_type == "daily":
            # 每日定时格式 HH:MM
            schedule.every().day.at(schedule_time).do(
                self.execute_task, task_data=task_data).tag(f"task_{task_id}")
        elif schedule_type == "interval":
            # 间隔时间格式（分钟）
            minutes = int(schedule_time)
            schedule.every(minutes).minutes.do(
                self.execute_task, task_data=task_data).tag(f"task_{task_id}")
        elif schedule_type == "once":
            # 一次性任务，格式为 YYYY-MM-DD HH:MM
            target_time = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")
            
            # 如果时间已过，则不添加
            if target_time <= datetime.now():
                return
                
            # 计算与当前时间的差值（秒）
            time_diff = (target_time - datetime.now()).total_seconds()
            
            # 使用schedule的一次性任务
            schedule.every(time_diff).seconds.do(
                self.execute_task, task_data=task_data).tag(f"task_{task_id}")
        
        # 存储任务信息
        self.tasks[task_id] = {
            "name": name,
            "device_type": device_type,
            "action": action,
            "value": value,
            "schedule_type": schedule_type,
            "schedule_time": schedule_time
        }
        
        print(f"[Scheduler] Added task: {name} (ID: {task_id})")
        
    def remove_task(self, task_id):
        """从调度器中移除任务"""
        if task_id in self.tasks:
            # 从schedule中移除
            schedule.clear(f"task_{task_id}")
            # 从内存中移除
            del self.tasks[task_id]
            print(f"[Scheduler] Removed task ID: {task_id}")
            
    def update_task(self, task_id, is_active, **kwargs):
        """更新任务状态或内容"""
        # 先从调度器中移除
        self.remove_task(task_id)
        
        # 如果任务被激活，重新添加到调度器
        if is_active:
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, device_type, action, value, schedule_type, schedule_time FROM scheduled_tasks WHERE id = ?", 
                (task_id,))
            task = cursor.fetchone()
            conn.close()
            
            if task:
                name, device_type, action, value, schedule_type, schedule_time = task
                # 使用传入的参数更新任务属性
                for key, val in kwargs.items():
                    if key == 'name': name = val
                    elif key == 'device_type': device_type = val
                    elif key == 'action': action = val
                    elif key == 'value': value = val
                    elif key == 'schedule_type': schedule_type = val
                    elif key == 'schedule_time': schedule_time = val
                
                self.add_task(task_id, name, device_type, action, value, schedule_type, schedule_time)
    
    def execute_task(self, task_data):
        """执行定时任务"""
        device_type = task_data["device_type"]
        action = task_data["action"]
        value = task_data["value"]
        
        # 根据设备类型发布到不同的主题
        if device_type == "temperature":
            topic = "home/sensor/temperature/control"
            data = {"action": action, "value": value}
        elif device_type == "lighting":
            topic = "home/sensor/lighting/control"
            data = {"action": action, "value": value}
        elif device_type == "security":
            topic = "home/security/status/control"
            data = {"action": action, "value": value}
        else:
            print(f"[Scheduler] Unknown device type: {device_type}")
            return
        
        # 发布控制命令
        try:
            self.client.publish(topic, json.dumps(data))
            print(f"[Scheduler] Executed task: {task_data['name']} - {device_type}/{action}={value}")
            
            # 发布任务执行通知
            notification = {
                "task_id": task_data["id"],
                "task_name": task_data["name"],
                "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success"
            }
            self.client.publish(self.topic + "/executed", json.dumps(notification))
            
            # 如果是一次性任务，执行后从数据库中标记为非活动
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            cursor.execute("SELECT schedule_type FROM scheduled_tasks WHERE id = ?", (task_data["id"],))
            result = cursor.fetchone()
            
            if result and result[0] == "once":
                cursor.execute("UPDATE scheduled_tasks SET is_active = 0 WHERE id = ?", (task_data["id"],))
                conn.commit()
                # 从内存中移除
                self.remove_task(task_data["id"])
                
            conn.close()
            
        except Exception as e:
            print(f"[Scheduler] Task execution error: {e}")
    
    def start(self):
        """启动调度器线程"""
        if self.scheduler_thread is None or not self.running:
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            print("[Scheduler] Scheduler started")
    
    def stop(self):
        """停止调度器线程"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
            print("[Scheduler] Scheduler stopped")
    
    def _run_scheduler(self):
        """运行调度器的内部方法"""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def publish_tasks_update(self):
        """发布当前任务列表更新"""
        conn = sqlite3.connect('smart_home.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, device_type, action, value, schedule_type, schedule_time, is_active FROM scheduled_tasks")
        tasks = cursor.fetchall()
        conn.close()
        
        tasks_list = []
        for task in tasks:
            task_id, name, device_type, action, value, schedule_type, schedule_time, is_active = task
            tasks_list.append({
                "id": task_id,
                "name": name,
                "device_type": device_type,
                "action": action,
                "value": value,
                "schedule_type": schedule_type,
                "schedule_time": schedule_time,
                "is_active": bool(is_active)
            })
        
        try:
            self.client.publish(self.topic, json.dumps({"tasks": tasks_list}))
            print(f"[Scheduler] Published tasks update: {len(tasks_list)} tasks")
        except Exception as e:
            print(f"[Scheduler] Publish error: {e}")


class SchedulerSubscriber:
    def __init__(self, client, scheduler_publisher):
        self.client = client
        self.scheduler_publisher = scheduler_publisher
        self.topic_base = "home/scheduler"
        
        # 订阅控制主题
        self.client.message_callback_add(f"{self.topic_base}/control", self.on_control_message)
        self.client.subscribe(f"{self.topic_base}/control")
        
    def on_control_message(self, client, userdata, msg):
        """处理控制消息"""
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            command = data.get("command")
            
            if command == "add_task":
                self._handle_add_task(data)
            elif command == "remove_task":
                self._handle_remove_task(data)
            elif command == "update_task":
                self._handle_update_task(data)
            elif command == "get_tasks":
                self._handle_get_tasks()
            else:
                print(f"[Scheduler] Unknown command: {command}")
                
        except json.JSONDecodeError:
            print(f"[Scheduler] Invalid control message")
        except Exception as e:
            print(f"[Scheduler] Control message error: {e}")
    
    def _handle_add_task(self, data):
        """处理添加任务请求"""
        try:
            name = data.get("name")
            device_type = data.get("device_type")
            action = data.get("action")
            value = data.get("value")
            schedule_type = data.get("schedule_type")
            schedule_time = data.get("schedule_time")
            
            # 验证必要字段
            if not all([name, device_type, action, schedule_type, schedule_time]):
                print("[Scheduler] Missing required fields for task creation")
                return
            
            # 添加到数据库
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scheduled_tasks (name, device_type, action, value, schedule_type, schedule_time, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
                (name, device_type, action, value, schedule_type, schedule_time)
            )
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # 添加到调度器
            self.scheduler_publisher.add_task(task_id, name, device_type, action, value, schedule_type, schedule_time)
            
            # 发布更新
            self.scheduler_publisher.publish_tasks_update()
            
        except Exception as e:
            print(f"[Scheduler] Add task error: {e}")
    
    def _handle_remove_task(self, data):
        """处理移除任务请求"""
        try:
            task_id = data.get("task_id")
            
            if not task_id:
                print("[Scheduler] Missing task_id for removal")
                return
            
            # 从数据库中移除或标记为非活动
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE scheduled_tasks SET is_active = 0 WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            
            # 从调度器中移除
            self.scheduler_publisher.remove_task(task_id)
            
            # 发布更新
            self.scheduler_publisher.publish_tasks_update()
            
        except Exception as e:
            print(f"[Scheduler] Remove task error: {e}")
    
    def _handle_update_task(self, data):
        """处理更新任务请求"""
        try:
            task_id = data.get("task_id")
            is_active = data.get("is_active", False)
            
            if not task_id:
                print("[Scheduler] Missing task_id for update")
                return
            
            # 更新数据库
            conn = sqlite3.connect('smart_home.db')
            cursor = conn.cursor()
            
            update_fields = []
            params = []
            
            for field in ["name", "device_type", "action", "value", "schedule_type", "schedule_time"]:
                if field in data:
                    update_fields.append(f"{field} = ?")
                    params.append(data[field])
            
            update_fields.append("is_active = ?")
            params.append(1 if is_active else 0)
            params.append(task_id)
            
            cursor.execute(
                f"UPDATE scheduled_tasks SET {', '.join(update_fields)} WHERE id = ?",
                tuple(params)
            )
            conn.commit()
            conn.close()
            
            # 更新调度器中的任务
            update_data = {k: v for k, v in data.items() 
                          if k in ["name", "device_type", "action", "value", "schedule_type", "schedule_time"]}
            self.scheduler_publisher.update_task(task_id, is_active, **update_data)
            
            # 发布更新
            self.scheduler_publisher.publish_tasks_update()
            
        except Exception as e:
            print(f"[Scheduler] Update task error: {e}")
    
    def _handle_get_tasks(self):
        """处理获取任务列表请求"""
        self.scheduler_publisher.publish_tasks_update() 
