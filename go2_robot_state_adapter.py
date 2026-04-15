#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import paho.mqtt.client as mqtt
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles


def quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Convert quaternion to planar yaw angle in radians."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def make_timestamped_csv_path(directory: str = "logs") -> str:
    """
    Create a timestamped CSV filename in the format:
    go2_vehicle_state_YY_MM_DD_HH_mm.csv
    """
    timestamp = datetime.now().strftime("%y_%m_%d_%H_%M")
    return str(Path(directory) / f"go2_vehicle_state_{timestamp}.csv")


@dataclass
class RobotState:
    robot_id: str
    seq: int

    source_timestamp_ns: int
    publish_time_ns: int

    x: float
    y: float
    z: float

    qx: float
    qy: float
    qz: float
    qw: float

    yaw: float

    v_linear_x: float
    v_linear_y: float
    v_linear_z: float

    v_angular_x: float
    v_angular_y: float
    v_angular_z: float

    frame_id: str
    child_frame_id: str

    source: str = "odom"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VehicleState:
    robot_id: str
    seq: int
    timestamp_ns: int
    publish_time_ns: int
    x: float
    y: float
    yaw: float
    v_linear: float
    v_angular: float

    def to_dict(self) -> dict:
        return asdict(self)


class Go2RobotStateAdapter(Node):
    def __init__(self) -> None:
        super().__init__("go2_robot_state_adapter")

        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("robot_id", "go2")
        self.declare_parameter("publish_rate_hz", 20.0)

        self.declare_parameter("csv_enabled", True)
        self.declare_parameter("csv_directory", "logs")

        self.declare_parameter("mqtt_enabled", True)
        self.declare_parameter("mqtt_broker", "127.0.0.1")
        self.declare_parameter("mqtt_port", 1883)
        self.declare_parameter("mqtt_topic", "go2/vehicle_state")
        self.declare_parameter("mqtt_client_id", "go2_robot_state_adapter")
        self.declare_parameter("mqtt_username", "")
        self.declare_parameter("mqtt_password", "")

        self.declare_parameter("print_robot_state", False)
        self.declare_parameter("print_vehicle_state", True)

        self.odom_topic = str(self.get_parameter("odom_topic").value)
        self.robot_id = str(self.get_parameter("robot_id").value)
        self.publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        self.csv_enabled = bool(self.get_parameter("csv_enabled").value)
        self.csv_directory = str(self.get_parameter("csv_directory").value)
        self.csv_filename = make_timestamped_csv_path(self.csv_directory)

        self.mqtt_enabled = bool(self.get_parameter("mqtt_enabled").value)
        self.mqtt_broker = str(self.get_parameter("mqtt_broker").value)
        self.mqtt_port = int(self.get_parameter("mqtt_port").value)
        self.mqtt_topic = str(self.get_parameter("mqtt_topic").value)
        self.mqtt_client_id = str(self.get_parameter("mqtt_client_id").value)
        self.mqtt_username = str(self.get_parameter("mqtt_username").value)
        self.mqtt_password = str(self.get_parameter("mqtt_password").value)

        self.print_robot_state = bool(self.get_parameter("print_robot_state").value)
        self.print_vehicle_state = bool(self.get_parameter("print_vehicle_state").value)

        self._lock = threading.Lock()
        self.latest_odom: Optional[Odometry] = None
        self.seq: int = 0
        self.last_publish_time_ns: Optional[int] = None

        qos_profile = QoSPresetProfiles.SENSOR_DATA.value
        self.subscription = self.create_subscription(
            Odometry,
            self.odom_topic,
            self.odom_callback,
            qos_profile,
        )

        self.csv_file = None
        self.csv_writer = None
        if self.csv_enabled:
            self._setup_csv()

        self.mqtt_client: Optional[mqtt.Client] = None
        if self.mqtt_enabled:
            self._setup_mqtt()

        period = 1.0 / max(self.publish_rate_hz, 1e-6)
        self.timer = self.create_timer(period, self.timer_callback)

        self.get_logger().info(
            f"Started Go2RobotStateAdapter | "
            f"odom_topic={self.odom_topic} | robot_id={self.robot_id} | "
            f"publish_rate_hz={self.publish_rate_hz} | "
            f"csv_enabled={self.csv_enabled} | csv_file={self.csv_filename} | "
            f"mqtt_enabled={self.mqtt_enabled}"
        )

    def _setup_csv(self) -> None:
        csv_path = Path(self.csv_filename)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        self.csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(
            [
                "seq",
                "robot_id",
                "timestamp_ns",
                "publish_time_ns",
                "publish_dt_ms",
                "x",
                "y",
                "yaw_rad",
                "yaw_deg",
                "v_linear",
                "v_angular",
            ]
        )
        self.csv_file.flush()

    def _setup_mqtt(self) -> None:
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.mqtt_client_id,
        )

        if self.mqtt_username:
            self.mqtt_client.username_pw_set(
                username=self.mqtt_username,
                password=self.mqtt_password,
            )

        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect

        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
        except Exception as exc:
            self.get_logger().error(
                f"MQTT connection failed to {self.mqtt_broker}:{self.mqtt_port}: {exc}"
            )
            self.mqtt_enabled = False
            self.mqtt_client = None

    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self.get_logger().info(
                f"MQTT connected to {self.mqtt_broker}:{self.mqtt_port}, "
                f"publishing to {self.mqtt_topic}"
            )
        else:
            self.get_logger().error(f"MQTT connect failed with reason_code={reason_code}")

    def on_mqtt_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.get_logger().warn(f"MQTT disconnected, reason_code={reason_code}")

    def odom_callback(self, msg: Odometry) -> None:
        with self._lock:
            self.latest_odom = msg

    def build_robot_state(self, msg: Odometry) -> RobotState:
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        twist = msg.twist.twist

        source_timestamp_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)
        publish_time_ns = time.time_ns()
        yaw = quat_to_yaw(ori.x, ori.y, ori.z, ori.w)

        return RobotState(
            robot_id=self.robot_id,
            seq=self.seq,
            source_timestamp_ns=source_timestamp_ns,
            publish_time_ns=publish_time_ns,
            x=float(pos.x),
            y=float(pos.y),
            z=float(pos.z),
            qx=float(ori.x),
            qy=float(ori.y),
            qz=float(ori.z),
            qw=float(ori.w),
            yaw=float(yaw),
            v_linear_x=float(twist.linear.x),
            v_linear_y=float(twist.linear.y),
            v_linear_z=float(twist.linear.z),
            v_angular_x=float(twist.angular.x),
            v_angular_y=float(twist.angular.y),
            v_angular_z=float(twist.angular.z),
            frame_id=str(msg.header.frame_id),
            child_frame_id=str(msg.child_frame_id),
        )

    def robot_to_vehicle_state(self, robot_state: RobotState) -> VehicleState:
        return VehicleState(
            robot_id=robot_state.robot_id,
            seq=robot_state.seq,
            timestamp_ns=robot_state.source_timestamp_ns,
            publish_time_ns=robot_state.publish_time_ns,
            x=robot_state.x,
            y=robot_state.y,
            yaw=robot_state.yaw,
            v_linear=robot_state.v_linear_x,
            v_angular=robot_state.v_angular_z,
        )

    def timer_callback(self) -> None:
        with self._lock:
            msg = self.latest_odom

        if msg is None:
            self.get_logger().warn("No /odom received yet")
            return

        robot_state = self.build_robot_state(msg)
        vehicle_state = self.robot_to_vehicle_state(robot_state)

        publish_dt_ms: Optional[float] = None
        if self.last_publish_time_ns is not None:
            publish_dt_ms = (vehicle_state.publish_time_ns - self.last_publish_time_ns) / 1e6
        self.last_publish_time_ns = vehicle_state.publish_time_ns

        if self.print_robot_state:
            self.get_logger().info(f"RobotState: {robot_state.to_dict()}")

        if self.print_vehicle_state:
            dt_text = "n/a" if publish_dt_ms is None else f"{publish_dt_ms:.2f} ms"
            self.get_logger().info(
                f"[VehicleState seq={vehicle_state.seq}] "
                f"id={vehicle_state.robot_id} | dt={dt_text} | "
                f"x={vehicle_state.x:.3f} y={vehicle_state.y:.3f} | "
                f"yaw={vehicle_state.yaw:.3f} rad ({math.degrees(vehicle_state.yaw):.1f} deg) | "
                f"v={vehicle_state.v_linear:.3f} m/s | "
                f"w={vehicle_state.v_angular:.3f} rad/s"
            )

        if self.csv_enabled:
            self._write_csv(vehicle_state, publish_dt_ms)

        if self.mqtt_enabled and self.mqtt_client is not None:
            self._publish_mqtt(vehicle_state)

        self.seq += 1

    def _write_csv(self, vehicle_state: VehicleState, publish_dt_ms: Optional[float]) -> None:
        if self.csv_writer is None or self.csv_file is None:
            return

        self.csv_writer.writerow(
            [
                vehicle_state.seq,
                vehicle_state.robot_id,
                vehicle_state.timestamp_ns,
                vehicle_state.publish_time_ns,
                "" if publish_dt_ms is None else f"{publish_dt_ms:.3f}",
                f"{vehicle_state.x:.6f}",
                f"{vehicle_state.y:.6f}",
                f"{vehicle_state.yaw:.6f}",
                f"{math.degrees(vehicle_state.yaw):.6f}",
                f"{vehicle_state.v_linear:.6f}",
                f"{vehicle_state.v_angular:.6f}",
            ]
        )
        self.csv_file.flush()

    def _publish_mqtt(self, vehicle_state: VehicleState) -> None:
        payload = json.dumps(vehicle_state.to_dict())

        try:
            info = self.mqtt_client.publish(self.mqtt_topic, payload=payload, qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                self.get_logger().warn(f"MQTT publish returned rc={info.rc}")
        except Exception as exc:
            self.get_logger().warn(f"MQTT publish failed: {exc}")

    def shutdown(self) -> None:
        if self.csv_file is not None:
            try:
                self.csv_file.close()
            except Exception:
                pass

        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Go2RobotStateAdapter()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down Go2RobotStateAdapter")
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()