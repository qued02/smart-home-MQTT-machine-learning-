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
done by Kaimin Wu
- Establishes secure MQTT connection (TLS)
- Initializes 3 simulated sensor publishers:
  - Temperature (value + comfort level)
  - Lighting (brightness + camera mode)
  - Security (lock status + noise suppression)
- Handles message subscription and database insertion
- Launches the Tkinter-based GUI
- Daily database cleanup and optimization

### `ui.py` - User Interface
done by Kaimin Wu
- Built using `tkinter + ttkbootstrap`
- Features:
  - Sliders for temperature and lighting
  - Dropdowns for camera modes and lock controls
  - Realtime dynamic charts (live updates)
  - History viewer with 1hr / 24hr / 7d filtering
- Notification system with categorized message levels
- Scene mode presets (e.g., "Sleep Mode")

### `publisher/temperature.py` - Intelligent Temperature Simulation  
done by Shihan Qu
- Simulates real-world temperature variations based on time of day, season, weather, and device heat
- Trains an Isolation Forest model using `scikit-learn` for anomaly detection on synthetic temperature data
- Assigns comfort levels (`cold`, `optimal`, `warm`, `hot`) based on real-time readings
- Publishes temperature, comfort level, and anomaly status to MQTT
- Includes trend-aware logic and early warning for overheat or sudden changes

### `publisher/security.py` - Context-Aware Security Prediction  
done by Shihan Qu
- Uses hour + weekday information to simulate smart lock and noise suppression behavior
- Implements Random Forest classifiers to predict lock status and noise setting with probabilistic reasoning
- Simulates behavior changes across working days and weekends
- Publishes predicted security states with confidence score to MQTT
- SecuritySubscriber module can identify suspicious patterns in long-term behavior

### `publisher/lighting.py` - Brightness Prediction via Polynomial Regression  
done by Shihan Qu
- Predicts indoor brightness as a quadratic function of time using polynomial regression
- Automatically generates training data (1000+ samples) to simulate light curve
- Standardizes input and trains model using `scikit-learn`
- Outputs predictive brightness values that dynamically adjust to user time context
- Enables integration with camera/motion logic or GUI-based brightness sliders
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
|👤 Behavior Modeling	| Simulate daily routines (wake-up, bedtime, absence hours)|
|🤖 Smarter Models | Use LSTM/Prophet for seasonal trend prediction|
|🧩 Scenario Automation	| Add IFTTT-style rule logic (e.g., auto-lock if door open at night)|
|🌐 Web Dashboard	| Add React/Flask dashboard with chart and control panels|
|📊 Time-Series DB	| Migrate from SQLite to InfluxDB or TimescaleDB for better logging|

## 💡 Acknowledgments

Powered by:

- [paho-mqtt](https://github.com/eclipse/paho.mqtt.python)  
- [matplotlib](https://matplotlib.org/)  
- [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap)  
- [scikit-learn](https://scikit-learn.org/)  
- [OpenWeatherMap API](https://openweathermap.org/api)  
- [Mosquitto MQTT Broker](https://test.mosquitto.org/)

---

## 📬 Contact

For suggestions, issues, or collaborations:

> 📧 wuk23@coventry.ac  
> 📌 GitHub: https://github.com/boin-go
> > 📧 qus6@coventry.ac  
> 📌 GitHub: https://github.com/qued02
