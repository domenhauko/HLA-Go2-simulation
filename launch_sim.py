#!/usr/bin/env python3
import subprocess
import shutil
import sys

SESSION = "turtlebot"


def run(cmd: str):
    subprocess.check_call(cmd, shell=True)


def main():
    if not shutil.which("tmux"):
        print("ERROR: tmux ni nameščen.", file=sys.stderr)
        sys.exit(1)

    # =========================
    # CHRONY TIME SYNC
    # =========================
    print("⏱ Syncing time with chrony...")
    subprocess.call("sudo systemctl enable chrony", shell=True)
    subprocess.call("sudo systemctl start chrony", shell=True)
    subprocess.call("chronyc tracking", shell=True)

    # =========================
    # TMUX SESSION
    # =========================
    subprocess.call(f"tmux kill-session -t {SESSION}", shell=True)
    run(f"tmux new-session -d -s {SESSION}")

    # split left/right → panes 0 (left) and 1 (right)
    run(f"tmux split-window -h -t {SESSION}:0.0")

    # left side: split into 3 panes → 0, 2, 3
    run(f"tmux split-window -v -t {SESSION}:0.0")
    run(f"tmux split-window -v -t {SESSION}:0.0")

    # right side: split into 2 panes → 1, 4
    run(f"tmux split-window -v -t {SESSION}:0.1")

    # Final pane layout:
    #  Left column:  0 (top), 2 (mid), 3 (bot)
    #  Right column: 1 (top), 4 (bot)

    # =========================
    # PANE 0 – GAZEBO (Classic 11, ROS2 Humble)
    # =========================
    run(f"""tmux send-keys -t {SESSION}:0.0 \
"source /opt/ros/humble/setup.bash && \
source ~/ros2_ws/install/setup.bash && \
ros2 launch turtlebot3_gazebo diff_robot_world.launch.py" C-m""")

    # =========================
    # PANE 1 – ROS–Gazebo BRIDGE
    # =========================
    run(f"""tmux send-keys -t {SESSION}:0.1 \
"source /opt/ros/humble/setup.bash && \
source ~/ros2_ws/install/setup.bash && \
ros2 run ros_gz_bridge parameter_bridge \
/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock \
/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist \
/model/diff_robot/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry \
/model/diff_robot/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V \
--ros-args -r /model/diff_robot/tf:=/tf" C-m""")

    # =========================
    # PANE 2 – STATIC TF
    # =========================
    run(f"""tmux send-keys -t {SESSION}:0.2 \
"source /opt/ros/humble/setup.bash && \
ros2 run tf2_ros static_transform_publisher \
0 0 0 0 0 0 world diff_robot/odom \
--ros-args -p use_sim_time:=true" C-m""")

    # =========================
    # PANE 3 – TELEOP (publishes to /cmd_vel_manual)
    # =========================
    run(f"""tmux send-keys -t {SESSION}:0.3 \
"source /opt/ros/humble/setup.bash && \
source ~/ros2_ws/install/setup.bash && \
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
--ros-args -r /cmd_vel:=/cmd_vel_manual" C-m""")

    # =========================
    # PANE 4 – MQTT ADAPTER (manual start)
    # =========================
    run(f"""tmux send-keys -t {SESSION}:0.4 \
"cd /home/dode/project && \
source mqtt_env/bin/activate && \
echo 'READY: run -> python3 odom_adapter_mqtt.py --ros-args -p use_sim_time:=true'" C-m""")

    print("✔  Pane 0 – Gazebo        (auto-started)")
    print("✔  Pane 1 – Bridge        (auto-started)")
    print("✔  Pane 2 – Static TF     (auto-started)")
    print("✔  Pane 3 – Teleop        (auto-started)")
    print("✔  Pane 4 – MQTT adapter  (manual – virtualenv ready)")
    print(f"\n➡  Attach with:  tmux attach -t {SESSION}")


if __name__ == "__main__":
    main()
