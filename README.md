# HLA-Go2-Simulation

A **Gazebo + ROS 2** simulation for the [Unitree Go2](https://www.unitree.com/go2/) robot, with an MQTT gateway bridging into an HLA simulation powered by [Portico RTI](https://github.com/openlvc/portico).

---

## 📋 Overview

```
Gazebo (Go2 simulation) → Teleoperation → /odom topic
    → MQTT Adapter → MQTT Broker → HLA Viewer
```

This project establishes a stable, transport-facing pipeline where robot odometry is captured, logged to CSV, and published as JSON over MQTT — forming the foundation for a full HLA gateway integration.

---

## ⚙️ Requirements

| Component | Version |
|-----------|---------|
| Ubuntu    | 22.04   |
| ROS 2     | Humble  |
| Gazebo    | 11.10.2 |

> **Note:** This setup is specifically built around the [anujjain-dev/unitree-go2-ros2](https://github.com/anujjain-dev/unitree-go2-ros2) repository, which only supports this exact combination of Ubuntu, ROS 2, and Gazebo.

### Check your versions
```bash
lsb_release -a          # Ubuntu
gazebo --version        # Gazebo
echo $ROS_DISTRO        # ROS 2
```

---

## 🚀 Setup

### Terminal 1 — Launch the Go2 Simulation

```bash
source /opt/ros/humble/setup.bash
source ~/go2_ws/install/setup.bash

# Standard launch
ros2 launch go2_config gazebo.launch.py rviz:=true

# With Velodyne lidar
ros2 launch go2_config gazebo_velodyne.launch.py rviz:=true
```

**Expected result:** Gazebo opens with the Go2 robot loaded.

---

### Terminal 2 — Teleoperate the Robot

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash

ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

**Expected result:** The Go2 moves in Gazebo and `/odom` updates accordingly.

---

### Terminal 3 — Monitor MQTT Messages

```bash
mosquitto_sub -h 127.0.0.1 -t go2/vehicle_state
```

**Expected result:** Terminal waits silently until the adapter starts publishing.

---

### Terminal 4 — Run the Compact ODOM Adapter

```bash
cd /path/to/your/project
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash

python3 compact_odom_adapter.py --ros-args \
  -p robot_id:=go2_001 \
  -p publish_rate_hz:=20.0 \
  -p csv_filename:=logs/go2_vehicle_state.csv \
  -p mqtt_broker:=127.0.0.1 \
  -p mqtt_port:=1883 \
  -p mqtt_topic:=go2/vehicle_state
```

**Parameters:**

| Parameter          | Description                                      |
|--------------------|--------------------------------------------------|
| `robot_id`         | Logical identifier for the robot                 |
| `publish_rate_hz`  | Fixed-rate publication/logging frequency (Hz)    |
| `csv_filename`     | Output CSV file path                             |
| `mqtt_broker`      | MQTT broker IP or hostname                       |
| `mqtt_port`        | MQTT broker port                                 |
| `mqtt_topic`       | Topic used for publishing JSON `VehicleState`    |

---

## ✅ Expected Outputs

### Adapter (Terminal 4)

On startup:
```
CompactOdomAdapter started | odom_topic=/odom | robot_id=go2_001 | publish_rate_hz=20.0 | csv_enabled=True | mqtt_enabled=True
MQTT connected to 127.0.0.1:1883, publishing to go2/vehicle_state
```

While running:
```
[VehicleState seq=1] id=go2_001 | dt=50.00 ms | x=0.012 y=0.001 | yaw=0.005 rad (0.3 deg) | v=0.250 m/s w=0.020 rad/s
```

- `seq` increments by 1 each cycle
- `dt` stays close to the configured publish period
- `x`, `y`, `yaw`, `v`, `w` change with robot motion

### MQTT Subscriber (Terminal 3)

```json
{
  "robot_id": "go2_001",
  "seq": 42,
  "timestamp_ns": 1712345678901234567,
  "publish_time_ns": 1712345678910000000,
  "x": 1.234,
  "y": -0.456,
  "yaw": 0.785,
  "v_linear": 0.600,
  "v_angular": 0.120
}
```

### CSV Log (`logs/go2_vehicle_state.csv`)

```
seq,robot_id,timestamp_ns,publish_time_ns,publish_dt_ms,x,y,yaw_rad,yaw_deg,v_linear,v_angular
```

- `seq` increases monotonically
- `publish_dt_ms` stays close to the configured publish period
- `yaw_rad` and `yaw_deg` are consistent with each other
- All values reflect live teleoperation input

---

## 🔧 Troubleshooting

<details>
<summary><strong>MQTT connection refused</strong></summary>

```
Error: Connection refused
```

The local MQTT broker is not running. Start it with:

```bash
sudo systemctl start mosquitto
```

Then retry `mosquitto_sub`.

</details>

<details>
<summary><strong>Adapter prints "No /odom received yet"</strong></summary>

The simulation is not running, or the topic name differs. Check available topics:

```bash
ros2 topic list
ros2 topic echo /odom
```

If the odom topic has a different name, pass it explicitly:

```bash
python3 compact_odom_adapter.py --ros-args \
  -p odom_topic:=/your_actual_odom_topic
```

</details>

<details>
<summary><strong>CSV is created but MQTT subscriber receives nothing</strong></summary>

Check the adapter terminal for this line:
```
MQTT connected to 127.0.0.1:1883, publishing to go2/vehicle_state
```

If missing, verify the broker IP, topic name, and that the broker is running.

</details>

<details>
<summary><strong>Robot moves in Gazebo but adapter values don't change</strong></summary>

You may be subscribed to the wrong odometry topic. Confirm `/odom` is the active stream:

```bash
ros2 topic echo /odom
```

</details>

---

## 📚 Resources

- [anujjain-dev/unitree-go2-ros2](https://github.com/anujjain-dev/unitree-go2-ros2) — base simulation repository
- [openlvc/portico](https://github.com/openlvc/portico) — Portico RTI (HLA implementation)
