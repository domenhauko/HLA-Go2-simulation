# HLA-Go2-Simulation

A ROS 2 + Gazebo simulation pipeline for the Unitree Go2 that publishes live robot pose over MQTT and bridges it into an HLA federation using Portico RTI.

---

## Current project status

The project currently supports the following end-to-end workflow:

- Run the Unitree Go2 simulation in Gazebo.
- Teleoperate the robot from the keyboard.
- Read live odometry from ROS 2.
- Publish `x`, `y`, and `yaw` through an MQTT adapter.
- Receive that data in an HLA gateway.
- Publish the pose into an HLA federation named `DemoFederation`.
- Visualize the robot in an HLA viewer as a **blue rectangle** with an **orange heading arrow**.
- Launch the main components through **VS Code tasks**.

This repository currently contains the main Python components for the odometry adapter, MQTT/HLA bridge, and HLA viewer, including `compact_odom_adapter.py`, `hla_gateway_receiver.py`, and `hla_viewer.py`. The repo also contains the working README and progress notes on the `dev` branch. citeturn199407view0

---

## System overview

```text
Gazebo (Unitree Go2) + ROS 2 Humble
        │
        ├── teleop_twist_keyboard
        │
        └── /odom
              │
              ▼
      compact_odom_adapter.py
              │
              ▼
          MQTT broker
              │
              ▼
      hla_gateway_receiver.py
              │
              ▼
     Portico RTI / DemoFederation
              │
              ▼
          hla_viewer.py
```

At the current stage, the HLA path focuses on robot pose visualization:

- `x`
- `y`
- `yaw`

The viewer uses these values to draw a simple 2D robot footprint and heading indication.

---

## Repository contents

Important files currently in the repository include:

- `compact_odom_adapter.py`
- `go2_odom_adapter.py`
- `go2_robot_state_adapter.py`
- `hla_gateway_receiver.py`
- `hla_viewer.py`
- `mqtt_gateway_receiver.py`
- `launch_sim.py`
- `README_project_progress.txt`

These files are visible in the current `dev` branch file tree. citeturn199407view0

---

## Requirements

| Component | Version |
|---|---:|
| Ubuntu | 22.04 |
| ROS 2 | Humble |
| Gazebo | 11.10.2 |
| Python | 3.10+ |
| Portico RTI | 2.1.4 |
| MQTT broker | Mosquitto or compatible |

The project is based on the Unitree Go2 Gazebo/ROS 2 setup from `anujjain-dev/unitree-go2-ros2`, and the current repository structure assumes that simulation workspace is available locally. The base repo this project depends on is referenced in the current README. fileciteturn10file0

---

## Current architecture notes

### ROS 2 / Gazebo side

The Go2 runs in Gazebo and publishes odometry through ROS 2. Teleoperation is done with `teleop_twist_keyboard`.

### MQTT transport

A compact odometry adapter converts ROS 2 odometry into a JSON vehicle-state message and publishes it to MQTT.

Typical fields include:

```json
{
  "robot_id": "go2_001",
  "seq": 42,
  "x": 1.234,
  "y": -0.456,
  "yaw": 0.785,
  "v_linear": 0.600,
  "v_angular": 0.120
}
```

### HLA side

`hla_gateway_receiver.py` receives the MQTT stream and publishes the pose into Portico RTI.

`hla_viewer.py` joins the same federation and renders the robot pose as:

- a blue rectangle for the robot body,
- an orange arrow for heading.

---

## How to run the current pipeline

The project is currently started through **VS Code tasks**.

Recommended startup order:

1. Start the Gazebo simulation.
2. Start teleoperation.
3. Start the MQTT adapter.
4. Start the HLA gateway.
5. Start the HLA viewer.

### 1. Gazebo simulation

Expected VS Code task behavior:

```bash
source /opt/ros/humble/setup.bash
source ~/go2_ws/install/setup.bash
ros2 launch go2_config gazebo.launch.py rviz:=true
```

### 2. Teleoperation

```bash
source /opt/ros/humble/setup.bash
source ~/go2_ws/install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

### 3. MQTT adapter

The current project includes odometry adapter scripts such as `compact_odom_adapter.py` and `go2_odom_adapter.py`. The active adapter should publish robot pose to the configured MQTT topic.

Example pattern:

```bash
python3 compact_odom_adapter.py --ros-args \
  -p robot_id:=go2_001 \
  -p publish_rate_hz:=20.0 \
  -p mqtt_broker:=127.0.0.1 \
  -p mqtt_port:=1883 \
  -p mqtt_topic:=go2/vehicle_state
```

### 4. HLA gateway

The HLA gateway is started with Portico environment variables set:

```bash
export RTI_HOME="/home/domen/Documents/LAK/portico-2.1.4"
export RTI_RID_FILE="/home/domen/Documents/LAK/Moja verzija/HLA-Go2-simulation/RTI.rid"
python3 "/home/domen/Documents/LAK/Moja verzija/HLA-Go2-simulation/hla_gateway_receiver.py"
```

### 5. HLA viewer

```bash
export RTI_HOME="/home/domen/Documents/LAK/portico-2.1.4"
export RTI_RID_FILE="/home/domen/Documents/LAK/Moja verzija/HLA-Go2-simulation/RTI.rid"
python3 "/home/domen/Documents/LAK/Moja verzija/HLA-Go2-simulation/hla_viewer.py"
```

---

## Current expected behavior

When the full pipeline is running:

- the Go2 moves in Gazebo,
- ROS 2 odometry updates continuously,
- the MQTT adapter publishes pose messages,
- the HLA gateway receives and republishes pose into the federation,
- the HLA viewer opens a matplotlib window,
- the robot is shown as a blue rectangle,
- the orange arrow indicates heading from `yaw`.

An image of the viewer will be added here later.

---

## Portico / HLA configuration

The project currently uses:

- **Portico RTI 2.1.4**
- **DemoFederation**
- a local `VehicleFOM.xml`
- a local `RTI.rid` file for Portico transport configuration

Both the gateway and viewer must use:

- the same `RTI_HOME`,
- the same `RTI_RID_FILE`,
- the same federation name,
- the same FOM.

---

## Known limitations of the current stage

This is the current working milestone, not the final architecture.

Current scope:

- Pose-only HLA visualization (`x`, `y`, `yaw`)
- Simple 2D viewer representation
- Local development workflow through VS Code tasks

Not yet documented here as fully complete:

- richer robot state in HLA,
- sensor federation,
- higher-level command/interaction classes,
- polished deployment scripts,
- screenshots and diagrams in the README.

---

## Troubleshooting

### `ros2 launch` or `ros2 run` command missing

A ROS 2 CLI package may be missing. Reinstall the required Humble packages, for example:

```bash
sudo apt update
sudo apt install ros-humble-ros2launch ros-humble-ros2run
```

### `robot_state_publisher` not found

Reinstall the package:

```bash
sudo apt install ros-humble-robot-state-publisher
```

### MQTT broker not running

```bash
sudo systemctl start mosquitto
```

### Portico not found

Make sure `RTI_HOME` points to the Linux Portico install containing `lib/portico.jar`.

### Gateway and viewer do not see each other

Make sure both use the same:

- `RTI_HOME`
- `RTI_RID_FILE`
- `VehicleFOM.xml`
- federation name

If Portico/JGroups still fails to connect over multicast, also verify the Linux multicast route and interface configuration.

---

## Resources

- Unitree Go2 product page: Unitree Go2. citeturn199407view0
- Base simulation dependency: `anujjain-dev/unitree-go2-ros2`. fileciteturn10file0
- Portico RTI: OpenLVC Portico. citeturn199407view0
- This repository (`dev` branch): `domenhauko/HLA-Go2-simulation`. citeturn199407view0
