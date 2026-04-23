# HLA-Go2-Simulation

A ROS 2 + Gazebo simulation pipeline for the Unitree Go2 that captures live robot state from `/odom`, logs it to CSV, publishes a compact vehicle-state message over MQTT, and bridges the pose into an HLA federation using Portico RTI.

---

## Current project status

The project currently supports the following end-to-end workflow:

- Run the Unitree Go2 simulation in Gazebo.
- Teleoperate the robot from the keyboard.
- Read live odometry from ROS 2.
- Convert odometry into a detailed `RobotState` structure.
- Log robot-state timing and motion data to CSV files.
- Convert the robot state into a compact `VehicleState` message.
- Publish `x`, `y`, `yaw`, `v_linear`, and `v_angular` through MQTT.
- Receive that data in an HLA gateway.
- Publish the pose into an HLA federation named `DemoFederation`.
- Visualize the robot in an HLA viewer as a blue rectangle with an orange heading indicator.
- Launch the main components through VS Code tasks or run the Python scripts directly.

This repository currently contains the working Python components for the ROS 2 state adapter, the MQTT/HLA bridge, and the HLA viewer, together with the HLA FOM and RTI configuration files used by the current `dev` branch.

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
      go2_robot_state_adapter.py
              │
              ├── CSV log file
              │
              └── MQTT: go2/vehicle_state
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

At the current stage, the HLA path focuses on robot pose visualization using the following attributes:

- `x`
- `y`
- `yaw`

The viewer subscribes to the HLA object updates and renders a simple 2D robot footprint and heading indicator.

---

## Repository contents

Important files currently in the repository include:

- `go2_robot_state_adapter.py` - ROS 2 node that subscribes to `/odom`, builds full robot-state data, writes CSV logs, and publishes compact vehicle-state messages to MQTT.
- `hla_gateway_receiver.py` - MQTT receiver that joins the HLA federation, registers a `Vehicle` object, and republishes `x`, `y`, and `yaw` into HLA.
- `hla_viewer.py` - HLA subscriber and live 2D viewer built with Matplotlib.
- `VehicleFOM.xml` - Federation Object Model defining the `Vehicle` object and its attributes.
- `RTI.rid` - Portico RTI configuration file.
- `.vscode/` - VS Code workspace settings and task definitions used to launch the current pipeline.
- `archive/` - older or experimental project files kept for reference.

---

## Requirements

| Component | Version / Notes |
|---|---|
| Ubuntu | 22.04 |
| ROS 2 | Humble |
| Gazebo | 11.x |
| Python | 3.10+ |
| Java | OpenJDK 11 |
| Portico RTI | 2.1.4 |
| MQTT broker | Mosquitto or compatible |
|

The project assumes that a working Unitree Go2 ROS 2/Gazebo simulation workspace is already available locally. This repository contains the integration layer that extracts robot state from ROS 2 and bridges it into MQTT and HLA.

---

## Current architecture notes

### ROS 2 / Gazebo side

The Go2 runs in Gazebo and publishes odometry through ROS 2. Teleoperation is done with `teleop_twist_keyboard`.

`go2_robot_state_adapter.py` subscribes to `/odom` using the ROS 2 sensor-data QoS profile and builds a detailed `RobotState` record containing:

- sequence number
- source timestamp
- adapter receive/publish timestamps
- position (`x`, `y`, `z`)
- orientation quaternion (`qx`, `qy`, `qz`, `qw`)
- planar yaw
- linear velocity components
- angular velocity components
- frame information

### CSV logging

The adapter can write timestamped CSV files to a `logs/` directory. These logs are useful for checking publish timing, latency, and vehicle motion during simulation runs.

Typical CSV fields include:

```text
seq, robot_id, source_timestamp_ns, adapter_receive_time_ns,
adapter_publish_time_ns, adapter_publish_monotonic_ns,
source_to_receive_ms, receive_to_publish_ms, publish_period_ms,
x, y, z, yaw_rad,
v_linear_x, v_linear_y, v_linear_z,
v_angular_x, v_angular_y, v_angular_z
```

### MQTT transport

The adapter converts the full robot state into a compact `VehicleState` message and publishes it to MQTT topic `go2/vehicle_state`.

Typical payload:

```json
{
  "robot_id": "go2",
  "seq": 42,
  "timestamp_ns": 1710000000000000000,
  "publish_time_ns": 1710000000100000000,
  "x": 1.234,
  "y": -0.456,
  "yaw": 0.785,
  "v_linear": 0.600,
  "v_angular": 0.120
}
```

### HLA side

`hla_gateway_receiver.py` receives the MQTT stream, joins `DemoFederation`, publishes the `HLAobjectRoot.Vehicle` object class, and updates the following attributes:

- `x`
- `y`
- `yaw`

`hla_viewer.py` joins the same federation, subscribes to those attributes, and renders the robot pose in a live Matplotlib window as:

- a blue rectangle for the robot body
- an orange heading line for orientation

---

## How to run the current pipeline

The project can be started through VS Code tasks or by running the scripts manually.

Recommended startup order:

1. Start the Gazebo simulation.
2. Start teleoperation.
3. Start the MQTT broker.
4. Start the Go2 robot-state adapter.
5. Start the HLA gateway.
6. Start the HLA viewer.

### 1. Gazebo simulation

Example:

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

### 3. MQTT broker

Example using Mosquitto:

```bash
mosquitto
```

### 4. Go2 robot-state adapter

```bash
source /opt/ros/humble/setup.bash
source ~/go2_ws/install/setup.bash
python3 go2_robot_state_adapter.py --ros-args \
  -p odom_topic:=/odom \
  -p robot_id:=go2 \
  -p publish_rate_hz:=20.0 \
  -p mqtt_enabled:=true \
  -p mqtt_broker:=127.0.0.1 \
  -p mqtt_port:=1883 \
  -p mqtt_topic:=go2/vehicle_state \
  -p csv_enabled:=true
```

### 5. HLA gateway

```bash
export RTI_HOME="/path/to/portico-2.1.4"
export RTI_RID_FILE="$(pwd)/RTI.rid"
python3 hla_gateway_receiver.py
```

### 6. HLA viewer

```bash
export RTI_HOME="/path/to/portico-2.1.4"
export RTI_RID_FILE="$(pwd)/RTI.rid"
python3 hla_viewer.py
```

---

## Current outputs

At the current stage, the project produces three useful outputs:

1. **ROS 2 console output** from the adapter showing the latest compact vehicle state.
2. **CSV log files** containing timing and motion data for each publish cycle.
3. **A live HLA viewer window** showing the simulated robot pose in 2D.

---

## Current limitations

The current `dev` branch is focused on validating the simulation-to-HLA data path, not on a full multi-entity federation model.

Current limitations include:

- HLA publication is currently limited to `x`, `y`, and `yaw`.
- The viewer is a simple 2D visualization intended for debugging and demonstration.
- The repository expects an external Go2 ROS 2/Gazebo simulation workspace to already be installed.
- Portico and Java paths still need to be configured correctly on the local machine.

---

## Next development direction

The natural next steps for this project are:

- expand the HLA data model beyond pose-only attributes
- publish richer robot state into the federation
- improve launch automation and packaging
- refine the viewer or connect the HLA stream to a more advanced external visualization client
- support multiple vehicles or federates in the same federation

---

## License

This project is licensed under the MIT License.