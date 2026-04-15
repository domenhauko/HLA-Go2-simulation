================================================================================
Go2 Gazebo → ROS 2 → Compact VehicleState Adapter (CSV + MQTT)
README.txt — Project Status, Setup, Launch Order, and Expected Results
================================================================================

1. PROJECT OVERVIEW
--------------------------------------------------------------------------------

This project is the first working phase of a larger pipeline whose final goal is:

    Gazebo (Go2) ↔ ROS 2 ↔ adapter (VehicleState/RobotState + sensors)
    ↔ transport ↔ gateway ↔ HLA (FOM)

At the current stage, the following parts are working:

    1) Unitree Go2 runs in Gazebo
    2) The robot can be teleoperated
    3) ROS 2 topics such as /odom are available
    4) A custom ROS 2 adapter subscribes to /odom
    5) The adapter builds a compact internal VehicleState
    6) VehicleState is logged to CSV
    7) VehicleState is published over MQTT as JSON
    8) A local Mosquitto broker can be used to verify the transport path

This README is written for a colleague who knows nothing about the project and
wants to reproduce the current state from scratch.

The current implementation is intentionally simple and focuses only on the first
outbound path:

    /odom → compact adapter → CSV log + MQTT JSON

It does NOT yet include:
    - HLA federation publishing
    - gateway-side processing
    - IMU integration
    - LiDAR integration
    - camera integration
    - command return path
    - AI safety logic

Those will be added later after the /odom → transport path is stable.


2. TARGET PLATFORM / KNOWN WORKING ENVIRONMENT
--------------------------------------------------------------------------------

The current setup is based on:

    OS:              Ubuntu 22.04
    ROS 2:           Humble
    Gazebo:          11.10.2
    Python:          Python 3
    MQTT broker:     Mosquitto
    Main robot sim:  Unitree Go2 Gazebo + ROS 2 stack

Reference repository used for the simulation setup:

    https://github.com/anujjain-dev/unitree-go2-ros2

Important project assumptions:

    - The Go2 simulation is already launchable in Gazebo
    - The robot can already be teleoperated
    - /odom is being published correctly
    - /imu/data exists, but is not yet used in this phase


3. CURRENT PROJECT GOAL
--------------------------------------------------------------------------------

The goal of this phase is to prove a clean and minimal transport-facing data path:

    Go2 in Gazebo
        ↓
    ROS 2 /odom
        ↓
    compact_odom_adapter.py
        ↓
    (A) CSV logging
    (B) MQTT JSON publishing

The adapter publishes a compact VehicleState with the following fields:

    robot_id
    seq
    timestamp_ns
    publish_time_ns
    x
    y
    yaw
    v_linear
    v_angular

These fields are enough for the next gateway-side stage.


4. FILES IN THIS PHASE
--------------------------------------------------------------------------------

You should have these Python scripts available locally:

    compact_odom_adapter.py
        Main ROS 2 adapter.
        Subscribes to /odom, builds compact VehicleState,
        logs to CSV, and publishes JSON over MQTT.

Optionally, during earlier testing we also used:

    go2_odom_subscriber.py
        Minimal subscriber used only to verify /odom.

    go2_odom_adapter.py
        Intermediate adapter version before compacting the state.

For the current phase, compact_odom_adapter.py is the main script.


5. DEPENDENCIES
--------------------------------------------------------------------------------

Install the required Ubuntu packages:

    sudo apt update
    sudo apt install -y \
        python3-pip \
        mosquitto \
        mosquitto-clients

Install Python dependencies:

    pip3 install paho-mqtt

ROS 2 dependencies are assumed to already be installed as part of your ROS 2
Humble environment and Go2 simulation workspace.

If ROS 2 Humble is not yet sourced, source it before running any scripts:

    source /opt/ros/humble/setup.bash

If your Go2 simulation is in a workspace, also source that workspace:

    source ~/ros2_ws/install/setup.bash

Adjust the workspace path above if your workspace has a different name.


6. GETTING THE GO2 SIMULATION
--------------------------------------------------------------------------------

Clone the repository used as the simulation base:

    git clone https://github.com/anujjain-dev/unitree-go2-ros2.git

Then follow that repository’s setup/build instructions.

This README assumes that after setup you can:

    - launch the Go2 in Gazebo
    - teleoperate the robot
    - inspect topics with:
        ros2 topic list
        ros2 topic echo /odom

Expected available topics at this stage:

    /odom
    /cmd_vel
    /tf
    /tf_static

Observed note:

    The IMU topic in this setup is named:

        /imu/data

It is not yet used by compact_odom_adapter.py.


7. VERIFY ROS 2 TOPICS BEFORE RUNNING THE ADAPTER
--------------------------------------------------------------------------------

Before using the adapter, confirm the simulation is publishing odometry.

Open a terminal and source ROS 2:

    source /opt/ros/humble/setup.bash
    source ~/go2_ws/install/setup.bash

List topics:

    ros2 topic list

Check odometry:

    ros2 topic echo /odom

You should see nav_msgs/msg/Odometry data changing while the robot moves.


8. START A LOCAL MQTT BROKER
--------------------------------------------------------------------------------

For the current phase, use a local broker first. This avoids cloud/network
problems and makes debugging easier.

Start Mosquitto:

    sudo systemctl start mosquitto

Check status:

    sudo systemctl status mosquitto

You can also enable it at boot:

    sudo systemctl enable mosquitto

At this point, a broker should be listening on:

    127.0.0.1:1883


9. TERMINAL ORDER FOR A CLEAN TEST
--------------------------------------------------------------------------------

Use the following terminal order.

------------------------------------------------------------------------------
TERMINAL 1 — Launch the Go2 simulation
------------------------------------------------------------------------------

Source ROS 2 and your workspace:

    source /opt/ros/humble/setup.bash
    source ~/go2_ws/install/setup.bash

Launch the Go2 simulation according to the repository instructions.

Example placeholder:

    <run the launch command required by the unitree-go2-ros2 repository>

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

Example placeholder:

    <run your teleop command here>
    
    ros2 run teleop_twist_keyboard teleop_twist_keyboard

If you already have a working teleop command, use that exact one.

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


13. NEXT PLANNED STEP
--------------------------------------------------------------------------------

The next recommended step is:

    MQTT receiver / gateway-side script

That receiver will:

    - subscribe to the same MQTT topic
    - parse the compact JSON VehicleState
    - print or validate received values
    - later serve as the input to the HLA gateway

After that, the project can move toward:

    compact VehicleState → gateway → HLA object publishing


14. REPRODUCTION CHECKLIST
--------------------------------------------------------------------------------

A colleague should consider the current phase successful if all of the following
are true:

    [ ] Ubuntu 22.04 is being used
    [ ] ROS 2 Humble is installed and sourced
    [ ] Gazebo 11.10.2 is installed
    [ ] Unitree Go2 simulation launches successfully
    [ ] The robot can be teleoperated
    [ ] /odom is visible via ros2 topic echo /odom
    [ ] Mosquitto is installed and running locally
    [ ] mosquitto_sub receives JSON messages on go2/vehicle_state
    [ ] compact_odom_adapter.py logs state messages continuously
    [ ] logs/go2_vehicle_state.csv is created and populated


15. NOTES
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
