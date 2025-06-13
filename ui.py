import ssl
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import paho.mqtt.client as mqtt
import json
import sqlite3
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
from threading import Thread
import queue
from tkinter import font
import ttkbootstrap as ttk
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']  # 设置中文字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题


class SmartHomeUI:
    def __init__(self, root):
        plt.switch_backend('TkAgg')
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        self.root = root
        self.root.title("MQTT智能家居控制系统")
        self.root.geometry("1200x800")

        # 使用与其他模块一致的MQTT配置
        self.broker = "test.mosquitto.org"
        self.port = 1883  # 使用非SSL端口
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
        
        # 由main.py设置的对象
        self.mqtt_client = None
        self.scheduler_pub = None
        self.ui_queue = None

        # 初始化UI
        self.setup_ui()

        # 连接MQTT
        self.setup_mqtt()

        # 启动队列检查
        self.root.after(100, self.process_queue)
        self.current_filter = "all"  # 当前通知过滤级别
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

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

    def setup_themes(self):
        style = ttk.Style()

        # 浅色主题
        style.configure('Light.TFrame', background='#f5f5f5')
        style.configure('Light.TLabel', background='#f5f5f5', foreground='#333')
        style.configure('Light.TButton', background='#e1e1e1', bordercolor='#ccc')

        # 深色主题
        style.configure('Dark.TFrame', background='#2d2d2d')
        style.configure('Dark.TLabel', background='#2d2d2d', foreground='#eee')
        style.configure('Dark.TButton', background='#3d3d3d', foreground='white')

        # 默认应用浅色主题
        self.apply_theme('light')

    def create_rounded_rect(canvas, x1, y1, x2, y2, radius=25, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius,
            x1 + radius, y1
        ]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def add_shadow(widget, offset=2, color='gray20'):
        shadow = tk.Frame(widget.master, bg=color)
        shadow.place(in_=widget, x=offset, y=offset,
                     width=widget.winfo_width(),
                     height=widget.winfo_height())
        widget.lift()  # 将主控件置于阴影上方

    def apply_theme(self, theme):
        bg = '#f5f5f5' if theme == 'light' else '#2d2d2d'
        self.root.config(bg=bg)
        for widget in self.root.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.Label)):
                widget.configure(style=f'{theme.capitalize()}.T{type(widget).__name__[1:]}')

    def setup_icons(self):
        icon_font = font.Font(family='FontAwesome', size=12)

        self.icons = {
            'lightbulb': '\uf0eb',  # 灯泡图标
            'thermometer': '\uf2c7',  # 温度计
            'lock': '\uf023',  # 锁
            'unlock': '\uf09c'  # 解锁
        }

        ttk.Button(self.toolbar,
                   text=f"{self.icons['lightbulb']} 灯光",
                   font=icon_font).pack(side=tk.LEFT)

    def setup_responsive_layout(self):
        # 主框架配置
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 使用grid权重实现自适应
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)

        # 窗口大小绑定事件
        self.root.bind('<Configure>', self.on_window_resize)

    def on_window_resize(self, event):
        width = event.width
        if width < 800:  # 小窗口布局
            self.sidebar.pack_forget()
            self.collapse_button.pack(side=tk.LEFT)
        else:  # 大窗口布局
            self.collapse_button.pack_forget()
            self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

    def create_collapsible_sidebar(self):
        self.sidebar = ttk.Frame(self.main_frame, width=200)
        self.sidebar.pack_propagate(False)

        # 折叠按钮
        self.collapse_button = ttk.Button(self.main_frame, text='☰',
                                          command=self.toggle_sidebar)

        # 侧边栏内容
        ttk.Label(self.sidebar, text="智能家居控制").pack(pady=10)
        self.device_list = ttk.Treeview(self.sidebar)
        self.device_list.pack(fill=tk.BOTH, expand=True)

    def toggle_sidebar(self):
        if self.sidebar.winfo_ismapped():
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

    def setup_enhanced_charts(self):
        # 创建双轴图表
        fig, ax1 = plt.subplots(figsize=(8, 4))
        ax2 = ax1.twinx()

        # 温度数据（折线图+渐变填充）
        temp_line = ax1.plot([], [], 'C0-', label='温度')[0]
        ax1.fill_between([], [], [], color='C0', alpha=0.1)

        # 湿度数据（柱状图）
        humidity_bars = ax2.bar([], [], width=0.8, alpha=0.3, color='C1')

        # 动画配置
        def update_chart(frame):
            temp_line.set_data(range(24), np.random.randint(15, 30, 24))
            ax1.collections[0].remove()  # 移除旧填充
            ax1.fill_between(range(24), np.random.randint(15, 30, 24),
                             color='C0', alpha=0.1)

            for bar, h in zip(humidity_bars, np.random.randint(30, 80, 24)):
                bar.set_height(h)

        self.ani = animation.FuncAnimation(fig, update_chart, frames=10, interval=1000)

    def animate_value_change(widget, start, end, duration=500):
        steps = 20
        delta = (end - start) / steps

        def _animate(step=0):
            current = start + delta * step
            widget.config(text=f"{current:.1f}°C")
            if step < steps:
                widget.after(duration // steps, _animate, step + 1)

        _animate()

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
        threshold_frame = ttk.Frame(frame)
        threshold_frame.pack(fill=tk.X)
        ttk.Label(threshold_frame, text="温度阈值:").pack(side=tk.LEFT)
        self.threshold_value = ttk.Label(threshold_frame, text="25.0°C")
        self.threshold_value.pack(side=tk.LEFT, padx=5)
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
        self.brightness_slider.configure(style='TickScale.Horizontal.TScale')
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
        
        # 定时任务标签页
        self.schedule_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.schedule_tab, text="定时任务")

        # 初始化图表
        self.setup_realtime_charts()
        self.setup_history_charts()
        self.setup_schedule_ui()

    def setup_realtime_charts(self):
        """实时数据图表"""
        chart_frame = ttk.Frame(self.realtime_tab)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 温度图表
        self.temp_fig, self.temp_ax = plt.subplots(figsize=(5, 3))
        self.temp_line, = self.temp_ax.plot([], [], 'b-')
        self.temp_ax.set_title("实时温度")
        self.temp_ax.set_ylabel("温度 (°C)")
        self.temp_ax.set_ylim(15, 35)
        self.temp_ax.grid(True)

        self.temp_canvas = FigureCanvasTkAgg(self.temp_fig, master=chart_frame)
        self.temp_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # 照明图表
        self.light_fig, self.light_ax = plt.subplots(figsize=(5, 3))
        self.light_bar = self.light_ax.bar([0], [80], width=0.6)
        self.light_ax.set_title("照明亮度")
        self.light_ax.set_ylabel("亮度 (%)")
        self.light_ax.set_ylim(0, 100)
        self.light_ax.grid(True)

        self.light_canvas = FigureCanvasTkAgg(self.light_fig, master=chart_frame)
        self.light_canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # 配置行列权重
        chart_frame.grid_rowconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(1, weight=1)

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

        filter_frame = ttk.Frame(self.notification_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        ttk.Button(filter_frame, text="全部",
                   command=lambda: self.filter_notifications("all")).pack(side=tk.LEFT)
        ttk.Button(filter_frame, text="信息",
                   command=lambda: self.filter_notifications("info")).pack(side=tk.LEFT)
        ttk.Button(filter_frame, text="警告",
                   command=lambda: self.filter_notifications("warning")).pack(side=tk.LEFT)
        ttk.Button(filter_frame, text="警报",
                   command=lambda: self.filter_notifications("alert")).pack(side=tk.LEFT)

        self.notification_list = tk.Listbox(
            self.notification_frame, height=4,
            selectmode=tk.SINGLE, background="#f0f0f0")
        self.notification_list.pack(fill=tk.X, padx=5, pady=5)

        filter_frame = ttk.Frame(self.notification_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        # 添加一些示例通知
        self.all_notifications = []
        self.add_notification("系统启动", "info")

    def filter_notifications(self, level):
        """根据级别过滤通知"""
        self.notification_list.delete(0, tk.END)
        for msg in self.all_notifications:
            if level == "all" or msg["level"] == level:
                self.notification_list.insert(0, f"[{msg['time']}] {msg['text']}")
                if msg["level"] == "warning":
                    self.notification_list.itemconfig(0, {'fg': 'orange'})
                elif msg["level"] == "alert":
                    self.notification_list.itemconfig(0, {'fg': 'red'})

    def setup_mqtt(self):
        """设置MQTT连接"""
        self.client = mqtt.Client(client_id="SmartHomeUI")

        # 添加TLS配置
        self.client.tls_set(
            ca_certs="mosquitto.org.crt",
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )

        self.client.on_connect = self.on_mqtt_connect
        self.client.on_message = self.on_mqtt_message

        try:
            # 注意端口改为8883（TLS默认端口）
            self.client.connect(self.broker, 8883, 60)
            self.client.loop_start()
        except Exception as e:
            messagebox.showerror("连接错误", f"无法连接到MQTT代理: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        if rc == 0:
            self.queue_message("update_status", {"connected": True})
            # 订阅所有主题
            client.subscribe(self.topics["temperature"], qos=1)  # 温度数据需要可靠
            client.subscribe(self.topics["lighting"], qos=1)  # 照明状态中等重要
            client.subscribe(self.topics["security"], qos=2)  # 安全警报最高优先级
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

    def setup_scene_controls(self):
        """场景模式控制"""
        frame = ttk.Labelframe(self.control_frame, text="场景模式")
        frame.pack(fill=tk.X, padx=5, pady=5)

        scenes = {
            "居家模式": {"brightness": 80, "temp": 22, "lock": "locked"},
            "睡眠模式": {"brightness": 20, "temp": 20, "lock": "locked"},
            "离家模式": {"brightness": 0, "temp": 18, "lock": "locked"}
        }

        for name, settings in scenes.items():
            btn = ttk.Button(frame, text=name,
                             command=lambda s=settings: self.apply_scene(s))
            btn.pack(side=tk.LEFT, padx=2)

    def queue_message(self, msg_type, data):
        """将消息放入队列供主线程处理"""
        self.message_queue.put((msg_type, data))

    def process_queue(self):
        """处理消息队列"""
        try:
            # 处理UI队列中的消息
            if hasattr(self, 'ui_queue') and self.ui_queue:
                while not self.ui_queue.empty():
                    msg_type, data = self.ui_queue.get_nowait()
                    
                    if msg_type == "update_temperature":
                        self.update_temperature_data(data)
                    elif msg_type == "update_lighting":
                        self.update_lighting_data(data)
                    elif msg_type == "update_security":
                        self.update_security_data(data)
                    elif msg_type == "update_schedule":
                        self.handle_schedule_update(data)
            
            # 处理内部消息队列
            while not self.message_queue.empty():
                msg_type, data = self.message_queue.get_nowait()
                
                if msg_type == "update_temperature":
                    self.update_temperature_data(data)
                elif msg_type == "update_lighting":
                    self.update_lighting_data(data)
                elif msg_type == "update_security":
                    self.update_security_data(data)
                elif msg_type == "connection_status":
                    self.update_connection_status(data)
        except Exception as e:
            print(f"处理消息队列错误: {e}")
        finally:
            # 继续检查队列
            self.root.after(100, self.process_queue)

    def update_connection_status(self, connected):
        """更新连接状态"""
        if connected:
            self.connection_status.config(text="已连接", foreground="green")
        else:
            self.connection_status.config(text="未连接", foreground="red")

    def update_temperature_data(self, data):
        """更新温度数据（兼容字典和浮点数输入）"""
        if isinstance(data, (int, float)):
            temp_data = {"temperature": float(data), "comfort_level": "optimal"}
        else:
            temp_data = data  # 假设已经是字典格式

        self.current_data["temperature"] = temp_data
        self.temp_var.set(f"{temp_data['temperature']:.1f} °C")

        # 更新温度图表（保持不变）
        temp = temp_data["temperature"]
        self.temp_line.set_data([0, 1], [temp, temp])
        self.temp_ax.relim()
        self.temp_ax.autoscale_view()
        self.temp_canvas.draw()

        # 检查温度警告
        if "comfort_level" in temp_data and temp_data["comfort_level"] == "high":
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
        try:
            data_type = self.data_type.get()
            time_range = self.time_range.get()

            if not data_type or not time_range:
                return

            data = self.get_history_data(data_type, time_range)

            self.history_ax.clear()

            if data_type == "temperature":
                self.plot_temperature_history(data)
            elif data_type == "lighting":
                self.plot_lighting_history(data)
            elif data_type == "security":
                self.plot_security_history(data)

            self.history_canvas.draw()

        except Exception as e:
            print(f"更新历史图表错误: {e}")
            self.history_ax.clear()
            self.history_ax.text(0.5, 0.5, f'错误: {str(e)}', ha='center')
            self.history_canvas.draw()

    def get_history_data(self, data_type, time_range):
        """从数据库获取历史数据"""
        conn = sqlite3.connect("smart_home.db")
        cursor = conn.cursor()

        # 使用更精确的时间条件
        if time_range == "1小时":
            time_condition = "timestamp >= datetime('now', '-1 hour')"
        elif time_range == "24小时":
            time_condition = "timestamp >= datetime('now', '-1 day')"
        else:  # 7天
            time_condition = "timestamp >= datetime('now', '-7 days')"

        try:
            if data_type == "temperature":
                cursor.execute(f"""
                    SELECT temperature, strftime('%Y-%m-%d %H:%M:%S', timestamp) 
                    FROM temperature 
                    WHERE {time_condition}
                    ORDER BY timestamp
                """)
            elif data_type == "lighting":
                cursor.execute(f"""
                    SELECT brightness, strftime('%Y-%m-%d %H:%M:%S', timestamp) 
                    FROM lighting 
                    WHERE {time_condition}
                    ORDER BY timestamp
                """)
            else:  # security
                cursor.execute(f"""
                    SELECT lock_status, strftime('%Y-%m-%d %H:%M:%S', timestamp) 
                    FROM security_status 
                    WHERE {time_condition}
                    ORDER BY timestamp
                """)
            return cursor.fetchall()
        except Exception as e:
            print(f"数据库查询错误: {e}")
            return []
        finally:
            conn.close()

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
        """绘制照明历史图表（亮度变化）"""
        self.history_ax.clear()  # 清空原有图表

        if not data:
            self.history_ax.text(0.5, 0.5, '无照明数据', ha='center')
            return

        # 解析数据：时间戳和亮度值（0-100%）
        timestamps = [datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S') for row in data]
        brightness = [row[0] for row in data]

        # 计算移动平均（7点）
        window_size = min(7, len(brightness))
        if window_size > 1:
            weights = np.repeat(1.0, window_size) / window_size
            ma = np.convolve(brightness, weights, 'valid')
            ma_timestamps = timestamps[window_size - 1:]
            self.history_ax.plot(ma_timestamps, ma, 'm-', label='7点移动平均', linewidth=2)  # 品红色

        # 绘制原始亮度数据（紫色半透明）
        self.history_ax.plot(timestamps, brightness, '#800080', alpha=0.3, label='原始亮度')

        # 添加统计信息
        avg_brightness = np.mean(brightness)
        max_brightness = max(brightness)
        min_brightness = min(brightness)
        self.history_ax.axhline(avg_brightness, color='c', linestyle='--',
                                label=f'平均 {avg_brightness:.1f}%')

        # 设置图表属性
        self.history_ax.set_ylim(0, 100)  # 亮度范围固定为0-100%
        self.history_ax.set_title(f"照明亮度历史 (最高: {max_brightness}%, 最低: {min_brightness}%)")
        self.history_ax.set_ylabel("亮度 (%)")
        self.history_ax.legend(loc='upper right')
        self.history_ax.grid(True, alpha=0.3)

        # 旋转x轴标签并自动调整间距
        for label in self.history_ax.get_xticklabels():
            label.set_rotation(45)
        self.history_ax.figure.tight_layout()

    def plot_security_history(self, data):
        """绘制安全历史图表"""
        if not data:  # 检查数据是否为空
            self.history_ax.clear()
            self.history_ax.text(0.5, 0.5, '无安全数据', ha='center')
            self.history_canvas.draw()
            return

        timestamps = [row[1] for row in data]
        lock_status = [1 if row[0] == "unlocked" else 0 for row in data]

        self.history_ax.clear()  # 先清空图表

        # 使用更兼容的绘图方式
        markerline, stemlines, baseline = self.history_ax.stem(
            range(len(timestamps)), lock_status, use_line_collection=True)

        # 设置x轴标签为时间
        self.history_ax.set_xticks(range(len(timestamps)))
        self.history_ax.set_xticklabels(timestamps)

        self.history_ax.set_title("门锁状态历史")
        self.history_ax.set_yticks([0, 1])
        self.history_ax.set_yticklabels(["锁定", "解锁"])
        self.history_ax.grid(True)

        # 旋转x轴标签
        for label in self.history_ax.get_xticklabels():
            label.set_rotation(45)

        self.history_ax.figure.tight_layout()

    def add_notification(self, message, level="info"):
        """添加系统通知"""
        now = datetime.now().strftime("%H:%M:%S")
        notification = {
            "time": now,
            "text": message,
            "level": level
        }
        self.all_notifications.insert(0, notification)

        # 只显示当前过滤级别的通知
        if hasattr(self, 'current_filter') and self.current_filter != "all":
            if level != self.current_filter:
                return

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

    def shutdown(self):
        plt.close('all')
        self.root.quit()

    def setup_schedule_ui(self):
        """设置定时任务管理界面"""
        if not hasattr(self, 'schedule_tab'):
            return
            
        # 分割定时任务界面为左右两部分
        self.schedule_paned = ttk.PanedWindow(self.schedule_tab, orient=tk.HORIZONTAL)
        self.schedule_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧：定时任务列表
        self.schedule_list_frame = ttk.LabelFrame(self.schedule_paned, text="定时任务列表")
        self.schedule_paned.add(self.schedule_list_frame, weight=1)
        
        # 右侧：添加/编辑定时任务
        self.schedule_edit_frame = ttk.LabelFrame(self.schedule_paned, text="添加/编辑定时任务")
        self.schedule_paned.add(self.schedule_edit_frame, weight=1)
        
        # 设置定时任务列表
        self.setup_schedule_list()
        
        # 设置定时任务编辑区域
        self.setup_schedule_editor()
    
    def setup_schedule_list(self):
        """设置定时任务列表"""
        # 创建工具栏
        toolbar = ttk.Frame(self.schedule_list_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # 添加按钮
        self.add_schedule_btn = ttk.Button(
            toolbar, text="添加任务", command=self.new_schedule)
        self.add_schedule_btn.pack(side=tk.LEFT, padx=2)
        
        self.refresh_schedule_btn = ttk.Button(
            toolbar, text="刷新", command=self.refresh_schedules)
        self.refresh_schedule_btn.pack(side=tk.LEFT, padx=2)
        
        # 创建列表
        columns = ("名称", "设备类型", "执行时间", "重复", "状态")
        self.schedule_tree = ttk.Treeview(
            self.schedule_list_frame, columns=columns, show="headings")
        
        # 设置列标题
        for col in columns:
            self.schedule_tree.heading(col, text=col)
            self.schedule_tree.column(col, width=100)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            self.schedule_list_frame, orient=tk.VERTICAL, command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.schedule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # 绑定双击事件
        self.schedule_tree.bind("<Double-1>", self.edit_selected_schedule)
        
        # 右键菜单
        self.schedule_menu = tk.Menu(self.schedule_tree, tearoff=0)
        self.schedule_menu.add_command(label="编辑", command=self.edit_selected_schedule)
        self.schedule_menu.add_command(label="删除", command=self.delete_selected_schedule)
        self.schedule_menu.add_separator()
        self.schedule_menu.add_command(label="启用/禁用", command=self.toggle_schedule_status)
        
        self.schedule_tree.bind("<Button-3>", self.show_schedule_menu)
        
        # 初始加载定时任务
        self.refresh_schedules()
    
    def setup_schedule_editor(self):
        """设置定时任务编辑区域"""
        # 创建表单
        form_frame = ttk.Frame(self.schedule_edit_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 名称
        ttk.Label(form_frame, text="任务名称:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.schedule_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.schedule_name_var).grid(
            row=0, column=1, sticky=tk.EW, pady=5)
        
        # 设备类型
        ttk.Label(form_frame, text="设备类型:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.device_type_var = tk.StringVar()
        device_types = ["temperature", "lighting", "security"]
        ttk.Combobox(form_frame, textvariable=self.device_type_var, 
                    values=device_types, state="readonly").grid(
            row=1, column=1, sticky=tk.EW, pady=5)
        
        # 执行时间
        ttk.Label(form_frame, text="执行时间:").grid(row=2, column=0, sticky=tk.W, pady=5)
        time_frame = ttk.Frame(form_frame)
        time_frame.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        self.hour_var = tk.StringVar()
        self.minute_var = tk.StringVar()
        
        # 小时选择器
        hours = [f"{h:02d}" for h in range(24)]
        ttk.Combobox(time_frame, textvariable=self.hour_var, values=hours, 
                    width=5, state="readonly").pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)
        
        # 分钟选择器
        minutes = [f"{m:02d}" for m in range(60)]
        ttk.Combobox(time_frame, textvariable=self.minute_var, values=minutes, 
                    width=5, state="readonly").pack(side=tk.LEFT)
        
        # 重复执行
        ttk.Label(form_frame, text="重复执行:").grid(row=3, column=0, sticky=tk.W, pady=5)
        repeat_frame = ttk.Frame(form_frame)
        repeat_frame.grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        self.repeat_vars = []
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        for i, day in enumerate(days):
            var = tk.BooleanVar()
            self.repeat_vars.append(var)
            ttk.Checkbutton(repeat_frame, text=day, variable=var).grid(
                row=0, column=i, padx=2)
        
        # 参数设置
        ttk.Label(form_frame, text="参数设置:").grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # 创建参数框架
        self.params_frame = ttk.Frame(form_frame)
        self.params_frame.grid(row=4, column=1, sticky=tk.EW, pady=5)
        
        # 设置参数UI的初始状态
        self.setup_empty_params_ui()
        
        # 绑定设备类型变更事件
        self.device_type_var.trace("w", self.on_device_type_change)
        
        # 按钮区域
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.save_btn = ttk.Button(button_frame, text="保存", command=self.save_schedule)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(button_frame, text="取消", command=self.clear_schedule_form)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # 当前编辑的定时任务ID
        self.current_schedule_id = None
        
        # 设置网格布局的列权重
        form_frame.columnconfigure(1, weight=1)
    
    def setup_empty_params_ui(self):
        """设置空参数UI"""
        # 清空参数框架
        for widget in self.params_frame.winfo_children():
            widget.destroy()
            
        ttk.Label(self.params_frame, text="请先选择设备类型").pack()
    
    def setup_temperature_params_ui(self):
        """设置温度参数UI"""
        # 清空参数框架
        for widget in self.params_frame.winfo_children():
            widget.destroy()
            
        # 温度参数
        ttk.Label(self.params_frame, text="温度值:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.temp_value_var = tk.DoubleVar(value=22.0)
        ttk.Spinbox(self.params_frame, from_=10, to=35, increment=0.5, 
                   textvariable=self.temp_value_var, width=10).grid(
            row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(self.params_frame, text="舒适度:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.comfort_level_var = tk.StringVar(value="optimal")
        comfort_levels = ["optimal", "warm", "cold"]
        ttk.Combobox(self.params_frame, textvariable=self.comfort_level_var, 
                    values=comfort_levels, state="readonly", width=10).grid(
            row=1, column=1, sticky=tk.W, pady=5)
    
    def setup_lighting_params_ui(self):
        """设置照明参数UI"""
        # 清空参数框架
        for widget in self.params_frame.winfo_children():
            widget.destroy()
            
        # 亮度参数
        ttk.Label(self.params_frame, text="亮度:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.brightness_var = tk.IntVar(value=80)
        ttk.Scale(self.params_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                 variable=self.brightness_var).grid(
            row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(self.params_frame, text="相机模式:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.camera_mode_var = tk.StringVar(value="auto")
        camera_modes = ["auto", "manual", "night"]
        ttk.Combobox(self.params_frame, textvariable=self.camera_mode_var, 
                    values=camera_modes, state="readonly").grid(
            row=1, column=1, sticky=tk.W, pady=5)
    
    def setup_security_params_ui(self):
        """设置安全参数UI"""
        # 清空参数框架
        for widget in self.params_frame.winfo_children():
            widget.destroy()
            
        # 锁状态参数
        ttk.Label(self.params_frame, text="锁状态:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.lock_status_var = tk.StringVar(value="locked")
        lock_statuses = ["locked", "unlocked"]
        ttk.Combobox(self.params_frame, textvariable=self.lock_status_var, 
                    values=lock_statuses, state="readonly").grid(
            row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(self.params_frame, text="降噪:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.noise_reduction_var = tk.StringVar(value="enabled")
        noise_reductions = ["enabled", "disabled"]
        ttk.Combobox(self.params_frame, textvariable=self.noise_reduction_var, 
                    values=noise_reductions, state="readonly").grid(
            row=1, column=1, sticky=tk.W, pady=5)
    
    def on_device_type_change(self, *args):
        """处理设备类型变更"""
        device_type = self.device_type_var.get()
        
        if device_type == "temperature":
            self.setup_temperature_params_ui()
        elif device_type == "lighting":
            self.setup_lighting_params_ui()
        elif device_type == "security":
            self.setup_security_params_ui()
        else:
            self.setup_empty_params_ui()
    
    def refresh_schedules(self):
        """刷新定时任务列表"""
        # 清空列表
        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)
            
        if not self.scheduler_pub:
            return
            
        # 获取所有定时任务
        schedules = self.scheduler_pub.get_all_schedules()
        
        # 添加到列表
        for schedule_id, schedule in schedules.items():
            # 格式化重复天数
            repeat_days = schedule.get('repeat_days', [])
            if not repeat_days:
                repeat_text = "不重复"
            else:
                days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                repeat_text = ", ".join([days[day] for day in repeat_days])
                
            # 状态
            status = "启用" if schedule.get('enabled', True) else "禁用"
            
            # 添加到树形列表
            self.schedule_tree.insert("", "end", iid=schedule_id, values=(
                schedule['name'],
                schedule['device_type'],
                schedule['schedule_time'],
                repeat_text,
                status
            ))
    
    def new_schedule(self):
        """创建新的定时任务"""
        self.current_schedule_id = None
        self.clear_schedule_form()
        
        # 设置默认值
        self.hour_var.set("08")
        self.minute_var.set("00")
        
        # 显示定时任务标签页
        self.notebook.select(self.schedule_tab)
    
    def edit_selected_schedule(self, event=None):
        """编辑选中的定时任务"""
        selected = self.schedule_tree.selection()
        if not selected:
            return
            
        schedule_id = int(selected[0])
        schedule = self.scheduler_pub.get_schedule(schedule_id)
        
        if not schedule:
            return
            
        # 设置表单值
        self.current_schedule_id = schedule_id
        self.schedule_name_var.set(schedule['name'])
        self.device_type_var.set(schedule['device_type'])
        
        # 设置时间
        time_parts = schedule['schedule_time'].split(":")
        self.hour_var.set(time_parts[0])
        self.minute_var.set(time_parts[1])
        
        # 设置重复天数
        for i in range(7):
            self.repeat_vars[i].set(i in schedule.get('repeat_days', []))
            
        # 设置参数
        self.on_device_type_change()  # 触发参数UI更新
        
        # 根据设备类型设置参数值
        device_type = schedule['device_type']
        params = schedule['parameters']
        
        if device_type == "temperature":
            self.temp_value_var.set(params.get('temperature', 22.0))
            self.comfort_level_var.set(params.get('comfort_level', 'optimal'))
        elif device_type == "lighting":
            self.brightness_var.set(params.get('brightness', 80))
            self.camera_mode_var.set(params.get('camera_mode', 'auto'))
        elif device_type == "security":
            self.lock_status_var.set(params.get('lock_status', 'locked'))
            self.noise_reduction_var.set(params.get('noise_reduction', 'enabled'))
        
        # 显示定时任务标签页
        self.notebook.select(self.schedule_tab)
    
    def save_schedule(self):
        """保存定时任务"""
        # 获取表单数据
        name = self.schedule_name_var.get()
        device_type = self.device_type_var.get()
        
        # 验证必填字段
        if not name or not device_type:
            messagebox.showerror("错误", "请填写任务名称和选择设备类型")
            return
            
        # 构建执行时间
        hour = self.hour_var.get()
        minute = self.minute_var.get()
        
        if not hour or not minute:
            messagebox.showerror("错误", "请设置执行时间")
            return
            
        schedule_time = f"{hour}:{minute}"
        
        # 获取重复天数
        repeat_days = []
        for i, var in enumerate(self.repeat_vars):
            if var.get():
                repeat_days.append(i)
                
        # 获取参数
        parameters = self.get_schedule_parameters()
        
        if not self.scheduler_pub:
            messagebox.showerror("错误", "调度器未初始化")
            return
            
        try:
            if self.current_schedule_id is None:
                # 添加新任务
                self.scheduler_pub.add_schedule(
                    name, device_type, "set", parameters, schedule_time, repeat_days)
                messagebox.showinfo("成功", "定时任务已添加")
            else:
                # 更新现有任务
                self.scheduler_pub.update_schedule(
                    self.current_schedule_id,
                    name=name,
                    device_type=device_type,
                    action="set",
                    parameters=parameters,
                    schedule_time=schedule_time,
                    repeat_days=repeat_days
                )
                messagebox.showinfo("成功", "定时任务已更新")
                
            # 刷新列表
            self.refresh_schedules()
            
            # 清空表单
            self.clear_schedule_form()
            
        except Exception as e:
            messagebox.showerror("错误", f"保存定时任务失败: {e}")
    
    def get_schedule_parameters(self):
        """根据设备类型获取参数"""
        device_type = self.device_type_var.get()
        
        if device_type == "temperature":
            return {
                "temperature": self.temp_value_var.get(),
                "comfort_level": self.comfort_level_var.get()
            }
        elif device_type == "lighting":
            return {
                "brightness": self.brightness_var.get(),
                "camera_mode": self.camera_mode_var.get()
            }
        elif device_type == "security":
            return {
                "lock_status": self.lock_status_var.get(),
                "noise_reduction": self.noise_reduction_var.get()
            }
        else:
            return {}
    
    def clear_schedule_form(self):
        """清空定时任务表单"""
        self.current_schedule_id = None
        self.schedule_name_var.set("")
        self.device_type_var.set("")
        self.hour_var.set("")
        self.minute_var.set("")
        
        for var in self.repeat_vars:
            var.set(False)
            
        self.setup_empty_params_ui()
    
    def delete_selected_schedule(self):
        """删除选中的定时任务"""
        selected = self.schedule_tree.selection()
        if not selected:
            return
            
        schedule_id = int(selected[0])
        
        if messagebox.askyesno("确认", "确定要删除选中的定时任务吗？"):
            if self.scheduler_pub.delete_schedule(schedule_id):
                self.refresh_schedules()
                
                # 如果正在编辑该任务，清空表单
                if self.current_schedule_id == schedule_id:
                    self.clear_schedule_form()
    
    def toggle_schedule_status(self):
        """切换定时任务状态（启用/禁用）"""
        selected = self.schedule_tree.selection()
        if not selected:
            return
            
        schedule_id = int(selected[0])
        schedule = self.scheduler_pub.get_schedule(schedule_id)
        
        if not schedule:
            return
            
        # 切换状态
        enabled = not schedule.get('enabled', True)
        
        if self.scheduler_pub.enable_schedule(schedule_id, enabled):
            self.refresh_schedules()
    
    def show_schedule_menu(self, event):
        """显示定时任务右键菜单"""
        item = self.schedule_tree.identify_row(event.y)
        if item:
            self.schedule_tree.selection_set(item)
            self.schedule_menu.post(event.x_root, event.y_root)
    
    def handle_schedule_update(self, data):
        """处理定时任务更新消息"""
        action = data.get('action')
        
        if action in ['add', 'update', 'delete']:
            self.refresh_schedules()
            
            # 如果正在编辑的任务被删除，清空表单
            if action == 'delete' and self.current_schedule_id == data.get('id'):
                self.clear_schedule_form()
                
            # 添加通知
            schedule_data = data.get('data', {})
            name = schedule_data.get('name', '未知任务')
            
            if action == 'add':
                self.add_notification(f"新增定时任务: {name}", "info")
            elif action == 'update':
                self.add_notification(f"更新定时任务: {name}", "info")
            elif action == 'delete':
                self.add_notification(f"删除定时任务: {name}", "warning")


if __name__ == "__main__":
    root = tk.Tk()
    app = SmartHomeUI(root)
    app.run()
