# 🏠 MQTT Smart Home Control System

This project is a Python-based smart home control system using the MQTT protocol. It integrates data publishing, real-time monitoring, historical data management, and a graphical user interface (GUI), ideal for teaching demos, prototyping, and IoT coursework.

---

## 🔧 Project Overview

### ✅ Key Features

| Feature | Description |
|---------|-------------|
| 🌐 MQTT Communication | Secure TLS connection to Mosquitto public broker, real-time data exchange |
| 📊 Real-Time Display | Live visualization of temperature, lighting, and security status |
| 💾 Local Database | SQLite for local storage and automatic data cleanup |
| 🖥 GUI Interface | Modern Tkinter-based interface with interactive controls |
| 🚪 Security Control | Toggle smart lock and noise suppression |
| 🌙 Scene Modes | One-click switch for "Home / Sleep / Away" presets |
| 🔔 Notification System | Info / Warning / Alert level notifications and filtering |

---

## 📂 File Structure

```
📦 Project Directory
├── main.py              # System entry point: MQTT, database, UI launch
├── ui.py                # GUI module (Tkinter)
├── publisher/           # Simulated sensor publishers
│   ├── temperature.py
│   ├── lighting.py
│   └── security.py
├── smart_home.db        # SQLite database (auto-generated)
└── mosquitto.org.crt    # MQTT TLS certificate
```

---

## ▶️ Quick Start

### ✅ Requirements

- Python 3.7+
- OS: Windows / macOS / Linux (GUI-capable)

### ✅ Install Dependencies

```bash
pip install paho-mqtt matplotlib ttkbootstrap numpy
```

### ✅ Run the Project

```bash
python main.py
```

> The system will connect to MQTT broker, start publishing simulated data, and launch the GUI.

---

## 📌 Module Highlights

### `main.py` - System Controller

- Establishes secure MQTT connection (TLS)
- Initializes 3 simulated sensor publishers:
  - Temperature (value + comfort level)
  - Lighting (brightness + camera mode)
  - Security (lock status + noise suppression)
- Handles message subscription and database insertion
- Launches the Tkinter-based GUI
- Daily database cleanup and optimization

### `ui.py` - User Interface

- Built using `tkinter + ttkbootstrap`
- Features:
  - Sliders for temperature and lighting
  - Dropdowns for camera modes and lock controls
  - Realtime dynamic charts (live updates)
  - History viewer with 1hr / 24hr / 7d filtering
- Notification system with categorized message levels
- Scene mode presets (e.g., "Sleep Mode")

---

## 📊 Sample Screenshots

> *(You may add screenshots here showing the GUI, charts, and controls.)*

---

## 🔐 MQTT Security Configuration

- Connects to Mosquitto test broker via TLS (port 8883)
- Uses `mosquitto.org.crt` as CA certificate
- Handles auto-reconnect and error alerts

---

## 🧠 Future Improvements

| Area | Suggestions |
|------|-------------|
| 🚀 User Auth | Add user login & access permissions |
| 📱 Mobile Access | Support Flask/web interface or WebSocket |
| ☁️ Cloud Sync | Connect with EMQX / AWS IoT / OneNet |
| 📈 Anomaly Alerts | Trigger warnings on extreme values |

---

## 💡 Acknowledgments

Powered by:

- [paho-mqtt](https://github.com/eclipse/paho.mqtt.python)
- [matplotlib](https://matplotlib.org/)
- [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap)
- [Mosquitto MQTT Broker](https://test.mosquitto.org/)

---

## 📬 Contact

For suggestions, issues, or collaborations:

> 📧 wuk23@coventry.ac  
> 📌 GitHub: https://github.com/boin-go
