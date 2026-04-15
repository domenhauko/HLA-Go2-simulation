# HLA-Go2-simulation
In this repository it is implemented a Gazebo and ROS2 based simulation for the Unitree Go2 robot as well as a MQTT gateway to a HLA simulation. HLA is implemented with Portico RTI.

## Resources
This project is based on a github repo https://github.com/anujjain-dev/unitree-go2-ros2 and uses Portico https://github.com/openlvc/portico

## Setup
This setup uses Ubuntu 22.04 and Gazebo version 11.10.2 and ROS2 Huumble. THe Anujjain repo is specifically written for this combination so unfortunatelly it doesn't work with other ROS2 versions.
(To check your versions: 
Ubuntu: lsb_release -a
Gazebo: gazebo --version
ROS: $echo ROS_DISTRO)

## Pipeline
GAZEBO simulation of Unitree Go2 robot and teleoperation -> MQTT adapter and receveiver for /odom topic -> HLA viewer

### Terminals setup
------------------------------------------------------------------------------
TERMINAL 1 — Launch the Go2 simulation
------------------------------------------------------------------------------

Source ROS 2 and your workspace:

    source /opt/ros/humble/setup.bash
    source ~/go2_ws/install/setup.bash

RUN:

	ros2 launch go2_config gazebo.launch.py rviz:=true
	
With Velodyne:
	
	ros2 launch go2_config gazebo_velodyne.launch.py rviz:=true

Note:
    The exact launch command depends on how you set up the repository.
    Use the command from your local Go2 simulation setup that already works.

Expected result:
    Gazebo opens and the Go2 robot appears.

------------------------------------------------------------------------------
TERMINAL 2 — Teleoperate the robot
------------------------------------------------------------------------------

Source ROS 2 and your workspace:

    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash

Run your teleoperation command.
    
    ros2 run teleop_twist_keyboard teleop_twist_keyboard

Expected result:
    The Go2 moves in Gazebo and /odom changes accordingly.

------------------------------------------------------------------------------
TERMINAL 3 — Verify MQTT messages with a subscriber
------------------------------------------------------------------------------

Run:

    mosquitto_sub -h 127.0.0.1 -t go2/vehicle_state

Expected result:
    This terminal waits silently until messages are published.

------------------------------------------------------------------------------
TERMINAL 4 — Run the compact adapter
------------------------------------------------------------------------------

Go to the folder containing compact_odom_adapter.py, then source ROS 2:

    cd /path/to/your/project
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash

Run the adapter:

    python3 compact_odom_adapter.py --ros-args \
      -p robot_id:=go2_001 \
      -p publish_rate_hz:=20.0 \
      -p csv_filename:=logs/go2_vehicle_state.csv \
      -p mqtt_broker:=127.0.0.1 \
      -p mqtt_port:=1883 \
      -p mqtt_topic:=go2/vehicle_state

Explanation of parameters:

    robot_id
        Logical identifier of the robot

    publish_rate_hz
        Fixed-rate publication/logging frequency of compact VehicleState

    csv_filename
        Output CSV file path

    mqtt_broker
        Broker IP or hostname

    mqtt_port
        Broker port

    mqtt_topic
        Topic used for publishing JSON VehicleState

10. EXPECTED OUTPUTS
--------------------------------------------------------------------------------

A) EXPECTED RESULT IN TERMINAL 4 (adapter)
------------------------------------------

When the adapter starts successfully, you should see something like:

    CompactOdomAdapter started | odom_topic=/odom | robot_id=go2_001 |
    publish_rate_hz=20.0 | csv_enabled=True | mqtt_enabled=True

When MQTT connects:

    MQTT connected to 127.0.0.1:1883, publishing to go2/vehicle_state

Then repeatedly while the simulation is running:

    [VehicleState seq=0] id=go2_001 | dt=n/a | x=0.000 y=0.000
    yaw=0.000 rad (0.0 deg) | v=0.000 m/s w=0.000 rad/s

    [VehicleState seq=1] id=go2_001 | dt=50.00 ms | x=0.012 y=0.001
    yaw=0.005 rad (0.3 deg) | v=0.250 m/s w=0.020 rad/s

The exact numbers will vary, but you should see:

    - seq increasing by 1
    - dt close to the chosen publish period
    - x and y changing when the robot moves
    - yaw changing when the robot turns
    - v and w changing with teleoperation

B) EXPECTED RESULT IN TERMINAL 3 (MQTT subscriber)
--------------------------------------------------

When the adapter is publishing, you should see JSON messages like:

    {"robot_id":"go2_001","seq":42,"timestamp_ns":1712345678901234567,
     "publish_time_ns":1712345678910000000,"x":1.234,"y":-0.456,
     "yaw":0.785,"v_linear":0.600,"v_angular":0.120}

The exact formatting may vary slightly, but the content should match the fields
above.

C) EXPECTED RESULT IN THE CSV FILE
----------------------------------

The adapter should create a CSV file at:

    logs/go2_vehicle_state.csv

The CSV header should look like:

    seq,robot_id,timestamp_ns,publish_time_ns,publish_dt_ms,x,y,yaw_rad,
    yaw_deg,v_linear,v_angular

Each row should contain one compact VehicleState sample.

Expected properties of the CSV:

    - seq increases monotonically
    - publish_dt_ms is close to the chosen publish period
    - x and y change with robot movement
    - yaw_rad and yaw_deg correspond correctly
    - v_linear and v_angular follow teleoperation

D) EXPECTED RESULT IN GAZEBO
----------------------------

When teleoperation is active:

    - the robot should move in the simulator
    - /odom should change accordingly
    - adapter output should reflect the motion
    - MQTT JSON and CSV logs should reflect the same motion

11. QUICK TROUBLESHOOTING
--------------------------------------------------------------------------------

Problem:
    mosquitto_sub -h 127.0.0.1 -t go2/vehicle_state
    returns:
        Error: Connection refused

Cause:
    No local MQTT broker is running.

Fix:
    Start Mosquitto:

        sudo systemctl start mosquitto

Then retry:

        mosquitto_sub -h 127.0.0.1 -t go2/vehicle_state

Problem:
    Adapter prints:
        No /odom received yet

Cause:
    The simulation is not running, or the topic name is different.

Fix:
    Check:

        ros2 topic list
        ros2 topic echo /odom

If the odom topic has a different name, run the adapter with:

    python3 compact_odom_adapter.py --ros-args \
      -p odom_topic:=/your_actual_odom_topic

Problem:
    CSV file is created, but MQTT subscriber shows nothing

Possible causes:
    - wrong broker IP
    - wrong topic
    - broker not running
    - adapter failed MQTT connect

Fix:
    Check adapter terminal for:

        MQTT connected to 127.0.0.1:1883, publishing to go2/vehicle_state

Problem:
    The robot moves in Gazebo but values do not change

Cause:
    The wrong topic is being subscribed to.

Fix:
    Confirm that /odom is the actual moving odometry stream.


12. WHAT HAS BEEN PROVEN SO FAR
--------------------------------------------------------------------------------

At this point, the following has been successfully demonstrated:

    - Go2 simulation runs in Gazebo
    - teleoperation works
    - /odom is readable from ROS 2
    - a ROS 2 node can subscribe to /odom
    - a compact transport-facing VehicleState can be built
    - the state can be logged to CSV
    - the state can be published as MQTT JSON
    - a local MQTT subscriber can receive the state

This is the first stable transport-facing milestone of the project.


13. NOTES
--------------------------------------------------------------------------------

This README documents only the current working milestone.

The implementation was intentionally kept simple to establish a stable base
before introducing:

    - protobuf / gRPC transport
    - HLA gateway integration
    - FOM mapping
    - IMU and other sensors
    - command return path
    - latency/jitter instrumentation beyond basic logging

Once the MQTT receiver is added and verified, the project can move into the
gateway and HLA integration phase.

================================================================================
END OF README
================================================================================
