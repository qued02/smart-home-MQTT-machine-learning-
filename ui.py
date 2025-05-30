import tkinter as tk
from tkinter import ttk, messagebox
import paho.mqtt.client as mqtt
import json
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
from threading import Thread
import queue


class SmartHomeUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MQTT智能家居控制系统")
        self.root.geometry("1200x800")

        # 使用与其他模块一致的MQTT配置
        self.broker = "test.mosquitto.org"
        self.port = 1883
        self.topics = {
            "temperature": "home/sensor/temperature",
            "lighting": "home/sensor/lighting",
            "security": "home/security/status"
        }

        # 数据存储 - 更新字段名与其他模块一致
        self.current_data = {
            "temperature": {"temperature": 22.0, "comfort_level": "optimal"},
            "lighting": {"brightness": 80, "camera_mode": "auto"},
            "security": {"lock_status": "locked", "noise_reduction": "enabled"}
        }

        # 消息队列用于线程安全更新UI
        self.message_queue = queue.Queue()

        # 初始化UI
        self.setup_ui()

        # 连接MQTT
        self.setup_mqtt()

        # 启动队列检查
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        """设置主界面布局"""
        # 顶部状态栏
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, padx=5, pady=5)

        self.connection_status = ttk.Label(
            self.status_bar, text="未连接", foreground="red")
        self.connection_status.pack(side=tk.LEFT)

        self.last_update = ttk.Label(
            self.status_bar, text="最后更新: 无")
        self.last_update.pack(side=tk.RIGHT)

        # 主内容区域
        self.main_panel = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_panel.pack(fill=tk.BOTH, expand=True)

        # 左侧控制面板
        self.control_frame = ttk.Labelframe(self.main_panel, text="设备控制", width=300)
        self.main_panel.add(self.control_frame)

        # 右侧数据显示区域
        self.display_frame = ttk.Frame(self.main_panel)
        self.main_panel.add(self.display_frame)

        # 初始化各组件
        self.setup_temperature_controls()
        self.setup_lighting_controls()
        self.setup_security_controls()
        self.setup_display_area()
        self.setup_notification_area()

    def setup_temperature_controls(self):
        """温度控制组件"""
        frame = ttk.Labelframe(self.control_frame, text="温度控制")
        frame.pack(fill=tk.X, padx=5, pady=5)

        # 温度显示
        self.temp_var = tk.StringVar(value="22.0 °C")
        ttk.Label(frame, textvariable=self.temp_var, font=('Arial', 14)).pack()

        # 舒适度状态
        self.comfort_var = tk.StringVar(value="舒适度: optimal")
        ttk.Label(frame, textvariable=self.comfort_var).pack()

        # 温度阈值设置
        ttk.Label(frame, text="温度阈值:").pack(anchor=tk.W)
        self.threshold_slider = ttk.Scale(
            frame, from_=15, to=35, value=25,
            command=lambda v: self.on_threshold_change(float(v)))
        self.threshold_slider.pack(fill=tk.X)

    def setup_lighting_controls(self):
        """照明控制组件"""
        frame = ttk.Labelframe(self.control_frame, text="照明控制")
        frame.pack(fill=tk.X, padx=5, pady=5)

        # 亮度控制
        ttk.Label(frame, text="亮度:").pack(anchor=tk.W)
        self.brightness_slider = ttk.Scale(
            frame, from_=0, to=100, value=80,
            command=lambda v: self.on_lighting_change("brightness", int(float(v))))
        self.brightness_slider.pack(fill=tk.X)

        # 相机调节模式 - 使用与LightingPublisher一致的选项
        ttk.Label(frame, text="相机模式:").pack(anchor=tk.W)
        self.camera_mode = ttk.Combobox(
            frame, values=["auto", "manual", "off"], state="readonly")
        self.camera_mode.set("auto")
        self.camera_mode.bind(
            "<<ComboboxSelected>>",
            lambda e: self.on_lighting_change("camera_mode", self.camera_mode.get()))
        self.camera_mode.pack(fill=tk.X)

    def setup_security_controls(self):
        """安全控制组件"""
        frame = ttk.Labelframe(self.control_frame, text="安全系统")
        frame.pack(fill=tk.X, padx=5, pady=5)

        # 智能门锁 - 更新字段名与SecurityPublisher一致
        self.lock_var = tk.StringVar(value="locked")
        ttk.Checkbutton(
            frame, text="智能门锁", variable=self.lock_var,
            onvalue="unlocked", offvalue="locked",
            command=lambda: self.on_security_change("lock_status", self.lock_var.get())
        ).pack(anchor=tk.W)

        # 噪音抑制
        self.noise_var = tk.StringVar(value="enabled")
        ttk.Checkbutton(
            frame, text="噪音抑制", variable=self.noise_var,
            onvalue="enabled", offvalue="disabled",
            command=lambda: self.on_security_change("noise_reduction", self.noise_var.get())
        ).pack(anchor=tk.W)

    def setup_display_area(self):
        """数据显示区域"""
        # 选项卡布局
        self.notebook = ttk.Notebook(self.display_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 实时数据标签页
        self.realtime_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.realtime_tab, text="实时数据")

        # 历史数据标签页
        self.history_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="历史数据")

        # 初始化图表
        self.setup_realtime_charts()
        self.setup_history_charts()

    def setup_realtime_charts(self):
        """实时数据图表"""
        frame = ttk.Frame(self.realtime_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 温度图表
        self.temp_fig, self.temp_ax = plt.subplots(figsize=(6, 3))
        self.temp_line, = self.temp_ax.plot([], [], 'b-')
        self.temp_ax.set_title("实时温度")
        self.temp_ax.set_ylabel("温度 (°C)")
        self.temp_ax.set_ylim(15, 35)
        self.temp_ax.grid(True)

        self.temp_canvas = FigureCanvasTkAgg(self.temp_fig, master=frame)
        self.temp_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 照明图表
        self.light_fig, self.light_ax = plt.subplots(figsize=(6, 3))
        self.light_bar = self.light_ax.bar([0], [80], width=0.6)
        self.light_ax.set_title("照明亮度")
        self.light_ax.set_ylabel("亮度 (%)")
        self.light_ax.set_ylim(0, 100)
        self.light_ax.grid(True)

        self.light_canvas = FigureCanvasTkAgg(self.light_fig, master=frame)
        self.light_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def setup_history_charts(self):
        """历史数据图表"""
        frame = ttk.Frame(self.history_tab)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 历史数据选择控件
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill=tk.X)

        ttk.Label(control_frame, text="数据类型:").pack(side=tk.LEFT)
        self.data_type = ttk.Combobox(
            control_frame, values=["temperature", "lighting", "security"], state="readonly")
        self.data_type.set("temperature")
        self.data_type.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="时间范围:").pack(side=tk.LEFT)
        self.time_range = ttk.Combobox(
            control_frame, values=["1小时", "24小时", "7天"], state="readonly")
        self.time_range.set("24小时")
        self.time_range.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame, text="查询",
            command=self.update_history_chart).pack(side=tk.LEFT)

        # 历史图表
        self.history_fig, self.history_ax = plt.subplots(figsize=(8, 5))
        self.history_canvas = FigureCanvasTkAgg(self.history_fig, master=frame)
        self.history_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 初始加载历史数据
        self.update_history_chart()

    def setup_notification_area(self):
        """通知区域"""
        self.notification_frame = ttk.Labelframe(self.root, text="系统通知")
        self.notification_frame.pack(fill=tk.X, padx=5, pady=5)

        self.notification_list = tk.Listbox(
            self.notification_frame, height=4,
            selectmode=tk.SINGLE, background="#f0f0f0")
        self.notification_list.pack(fill=tk.X, padx=5, pady=5)

        # 添加一些示例通知
        self.add_notification("系统启动", "info")

    def setup_mqtt(self):
        """设置MQTT连接"""
        self.client = mqtt.Client(client_id="SmartHomeUI")
        self.client.on_connect = self.on_mqtt_connect
        self.client.on_message = self.on_mqtt_message

        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            messagebox.showerror("连接错误", f"无法连接到MQTT代理: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        if rc == 0:
            self.queue_message("update_status", {"connected": True})
            # 订阅所有主题
            for topic in self.topics.values():
                client.subscribe(topic)
        else:
            self.queue_message("update_status", {"connected": False})

    def on_mqtt_message(self, client, userdata, msg):
        """MQTT消息回调"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic

            if topic == self.topics["temperature"]:
                self.queue_message("update_temperature", payload)
            elif topic == self.topics["lighting"]:
                self.queue_message("update_lighting", payload)
            elif topic == self.topics["security"]:
                self.queue_message("update_security", payload)

        except json.JSONDecodeError:
            print("无效的JSON数据")

    def queue_message(self, msg_type, data):
        """将消息放入队列供主线程处理"""
        self.message_queue.put((msg_type, data))

    def process_queue(self):
        """处理消息队列中的消息"""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == "update_status":
                    self.update_connection_status(data["connected"])
                elif msg_type == "update_temperature":
                    self.update_temperature_data(data)
                elif msg_type == "update_lighting":
                    self.update_lighting_data(data)
                elif msg_type == "update_security":
                    self.update_security_data(data)

        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    def update_connection_status(self, connected):
        """更新连接状态"""
        if connected:
            self.connection_status.config(text="已连接", foreground="green")
        else:
            self.connection_status.config(text="未连接", foreground="red")

    def update_temperature_data(self, data):
        """更新温度数据"""
        self.current_data["temperature"] = data
        self.temp_var.set(f"{data['temperature']:.1f} °C")
        self.comfort_var.set(f"舒适度: {data['comfort_level']}")

        # 更新温度图表
        temp = data["temperature"]
        self.temp_line.set_data([0, 1], [temp, temp])
        self.temp_ax.relim()
        self.temp_ax.autoscale_view()
        self.temp_canvas.draw()

        # 检查温度警告
        if data["comfort_level"] == "high":
            self.add_notification(f"高温警告: {temp}°C", "warning")

        self.update_last_update_time()

    def update_lighting_data(self, data):
        """更新照明数据"""
        self.current_data["lighting"] = data
        self.brightness_slider.set(data["brightness"])
        self.camera_mode.set(data["camera_mode"])

        # 更新照明图表
        for rect in self.light_bar:
            rect.set_height(data["brightness"])
        self.light_ax.relim()
        self.light_ax.autoscale_view()
        self.light_canvas.draw()

        self.update_last_update_time()

    def update_security_data(self, data):
        """更新安全数据"""
        self.current_data["security"] = data
        self.lock_var.set(data["lock_status"])
        self.noise_var.set(data["noise_reduction"])

        # 检查门锁状态变化
        if data["lock_status"] == "unlocked":
            self.add_notification("门锁已解锁", "alert")

        self.update_last_update_time()

    def update_last_update_time(self):
        """更新最后更新时间"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_update.config(text=f"最后更新: {now}")

    def update_history_chart(self):
        """更新历史图表"""
        data_type = self.data_type.get()
        time_range = self.time_range.get()

        # 从数据库获取数据
        data = self.get_history_data(data_type, time_range)

        # 清除旧图表
        self.history_ax.clear()

        if data_type == "temperature":
            self.plot_temperature_history(data)
        elif data_type == "lighting":
            self.plot_lighting_history(data)
        elif data_type == "security":
            self.plot_security_history(data)

        self.history_canvas.draw()

    def get_history_data(self, data_type, time_range):
        """从数据库获取历史数据"""
        conn = sqlite3.connect("smart_home.db")
        cursor = conn.cursor()

        # 根据时间范围计算时间条件
        if time_range == "1小时":
            time_condition = "datetime(timestamp) >= datetime('now', '-1 hour')"
        elif time_range == "24小时":
            time_condition = "datetime(timestamp) >= datetime('now', '-1 day')"
        else:  # 7天
            time_condition = "datetime(timestamp) >= datetime('now', '-7 days')"

        if data_type == "temperature":
            cursor.execute(f"""
                SELECT temperature, timestamp 
                FROM temperature 
                WHERE {time_condition}
                ORDER BY timestamp
            """)
            return cursor.fetchall()
        elif data_type == "lighting":
            cursor.execute(f"""
                SELECT brightness, timestamp 
                FROM lighting 
                WHERE {time_condition}
                ORDER BY timestamp
            """)
            return cursor.fetchall()
        else:  # security
            cursor.execute(f"""
                SELECT lock_status, timestamp 
                FROM security_status 
                WHERE {time_condition}
                ORDER BY timestamp
            """)
            return cursor.fetchall()

    def plot_temperature_history(self, data):
        """绘制温度历史图表"""
        timestamps = [row[1] for row in data]
        temps = [row[0] for row in data]

        self.history_ax.plot(timestamps, temps, 'b-')
        self.history_ax.set_title("温度历史")
        self.history_ax.set_ylabel("温度 (°C)")
        self.history_ax.grid(True)

        # 旋转x轴标签
        for label in self.history_ax.get_xticklabels():
            label.set_rotation(45)

    def plot_lighting_history(self, data):
        """绘制照明历史图表"""
        timestamps = [row[1] for row in data]
        brightness = [row[0] for row in data]

        self.history_ax.bar(timestamps, brightness, width=0.02)
        self.history_ax.set_title("照明亮度历史")
        self.history_ax.set_ylabel("亮度 (%)")
        self.history_ax.grid(True)

        for label in self.history_ax.get_xticklabels():
            label.set_rotation(45)

    def plot_security_history(self, data):
        """绘制安全历史图表"""
        timestamps = [row[1] for row in data]
        lock_status = [1 if row[0] == "unlocked" else 0 for row in data]

        self.history_ax.stem(timestamps, lock_status, use_line_collection=True)
        self.history_ax.set_title("门锁状态历史")
        self.history_ax.set_yticks([0, 1])
        self.history_ax.set_yticklabels(["锁定", "解锁"])
        self.history_ax.grid(True)

        for label in self.history_ax.get_xticklabels():
            label.set_rotation(45)

    def add_notification(self, message, level="info"):
        """添加系统通知"""
        now = datetime.now().strftime("%H:%M:%S")
        self.notification_list.insert(0, f"[{now}] {message}")

        # 根据级别设置颜色
        if level == "warning":
            self.notification_list.itemconfig(0, {'fg': 'orange'})
        elif level == "alert":
            self.notification_list.itemconfig(0, {'fg': 'red'})

        # 限制通知数量
        if self.notification_list.size() > 10:
            self.notification_list.delete(10, tk.END)

    def on_threshold_change(self, value):
        """温度阈值变化回调"""
        # 这里可以添加MQTT发布逻辑
        print(f"温度阈值更改为: {value}")

    def on_lighting_change(self, key, value):
        """照明设置变化回调"""
        # 更新本地数据
        self.current_data["lighting"][key] = value

        # 发布MQTT消息
        try:
            self.client.publish(
                self.topics["lighting"],
                json.dumps(self.current_data["lighting"]))
        except Exception as e:
            messagebox.showerror("发布错误", f"无法发布照明设置: {e}")

    def on_security_change(self, key, value):
        """安全设置变化回调"""
        # 更新本地数据
        self.current_data["security"][key] = value

        # 发布MQTT消息
        try:
            self.client.publish(
                self.topics["security"],
                json.dumps(self.current_data["security"]))
        except Exception as e:
            messagebox.showerror("发布错误", f"无法发布安全设置: {e}")

    def run(self):
        """运行主循环"""
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartHomeUI(root)
    app.run()