# Smart Greenhouse — Final Project

**IoT-based smart greenhouse system** for sensor monitoring, actuator control, data visualization, and **plant image analysis** (growth tracking and disease classification). Automated monitoring and control system for optimal plant growth.

## Overview

The Smart Greenhouse is an IoT-based system that automates and optimizes the environmental conditions of a greenhouse. It utilizes a Raspberry Pi 5 to monitor temperature, humidity, soil moisture, and light levels while controlling irrigation, ventilation, and lighting accordingly.

In addition to real-time monitoring and control, the system includes a data layer for analysis and traceability. All sensor readings and actuator states are persisted over time, enabling historical analysis and visualization through a dashboard. Plant images are stored and processed to extract growth metrics (pixel-based and percentage evolution) and to perform plant disease classification using a convolutional neural network (CNN).

This data-driven approach allows the greenhouse to move beyond simple automation, providing decision support, performance tracking, and continuous optimization based on historical trends and image-based insights.

## Key Features
- **Monitoring**: collection and historization of sensor data (temperature, humidity, light, etc.).
- **Control**: actuators (UV / irrigation / ventilation) with **manual** and **automatic** modes (threshold-based).
- **Dashboard**: real-time charts and actuator status.
- **Computer Vision**: plant image analysis (growth in pixels / % and disease classification using a CNN).
- **MQTT**: centralized topic management (see `mqtt_topics.*`).

## Tech Stack
- **Backend**: Python (Flask)
- **Frontend**: React
- **IoT Messaging**: MQTT
- **Data / Assets**: JSON + plant images (e.g. `plant_data.json`)

## Repository Structure
- `smart-greenhouse-backend/` — backend API  
- `smart-greenhouse-login/` — frontend / login interface  
- `python/` — Python scripts and utilities  
- `Creation_model.ipynb` — model training and experimentation notebook  
- `plant_data.json` — plant data and analysis history  
- `mqtt_topics.json` / `mqtt_topics.txt` — MQTT topic definitions  

## Installation & Run (Local)
### 1) Backend
```bash
cd smart-greenhouse-backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
