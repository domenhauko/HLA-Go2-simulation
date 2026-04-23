#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import paho.mqtt.client as mqtt
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles


def quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


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


class CompactOdomAdapter(Node):
    def __init__(self) -> None:
        super().__init__("compact_odom_adapter")

        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("robot_id", "go2")
        self.declare_parameter("publish_rate_hz", 10.0)

        self.declare_parameter("csv_enabled", True)
        self.declare_parameter("csv_filename", "vehicle_state_log.csv")

        self.declare_parameter("mqtt_enabled", True)
        self.declare_parameter("mqtt_broker", "127.0.0.1")
        self.declare_parameter("mqtt_port", 1883)
        self.declare_parameter("mqtt_topic", "go2/vehicle_state")
        self.declare_parameter("mqtt_client_id", "go2_odom_adapter")
        self.declare_parameter("mqtt_username", "")
        self.declare_parameter("mqtt_password", "")

        self.odom_topic = str(self.get_parameter("odom_topic").value)
        self.robot_id = str(self.get_parameter("robot_id").value)
        self.publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        self.csv_enabled = bool(self.get_parameter("csv_enabled").value)
        self.csv_filename = str(self.get_parameter("csv_filename").value)

        self.mqtt_enabled = bool(self.get_parameter("mqtt_enabled").value)
        self.mqtt_broker = str(self.get_parameter("mqtt_broker").value)
        self.mqtt_port = int(self.get_parameter("mqtt_port").value)
        self.mqtt_topic = str(self.get_parameter("mqtt_topic").value)
        self.mqtt_client_id = str(self.get_parameter("mqtt_client_id").value)
        self.mqtt_username = str(self.get_parameter("mqtt_username").value)
        self.mqtt_password = str(self.get_parameter("mqtt_password").value)

        self._lock = threading.Lock()
        self.latest_odom: Optional[Odometry] = None
        self.seq = 0
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
        self.timer = self.create_timer(period, self.publish_state)

        self.get_logger().info(
            f"CompactOdomAdapter started | "
            f"odom_topic={self.odom_topic} | robot_id={self.robot_id} | "
            f"publish_rate_hz={self.publish_rate_hz} | "
            f"csv_enabled={self.csv_enabled} | mqtt_enabled={self.mqtt_enabled}"
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

    def build_vehicle_state(self, msg: Odometry) -> VehicleState:
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        twist = msg.twist.twist

        timestamp_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)
        publish_time_ns = time.time_ns()
        yaw = quat_to_yaw(ori.x, ori.y, ori.z, ori.w)

        return VehicleState(
            robot_id=self.robot_id,
            seq=self.seq,
            timestamp_ns=timestamp_ns,
            publish_time_ns=publish_time_ns,
            x=float(pos.x),
            y=float(pos.y),
            yaw=float(yaw),
            v_linear=float(twist.linear.x),
            v_angular=float(twist.angular.z),
        )

    def publish_state(self) -> None:
        with self._lock:
            msg = self.latest_odom

        if msg is None:
            self.get_logger().warn("No /odom received yet")
            return

        state = self.build_vehicle_state(msg)

        publish_dt_ms = None
        if self.last_publish_time_ns is not None:
            publish_dt_ms = (state.publish_time_ns - self.last_publish_time_ns) / 1e6
        self.last_publish_time_ns = state.publish_time_ns

        if self.csv_enabled:
            self._write_csv(state, publish_dt_ms)

        if self.mqtt_enabled and self.mqtt_client is not None:
            self._publish_mqtt(state)

        dt_text = "n/a" if publish_dt_ms is None else f"{publish_dt_ms:.2f} ms"
        self.get_logger().info(
            f"[VehicleState seq={state.seq}] "
            f"id={state.robot_id} | dt={dt_text} | "
            f"x={state.x:.3f} y={state.y:.3f} yaw={state.yaw:.3f} rad "
            f"({math.degrees(state.yaw):.1f} deg) | "
            f"v={state.v_linear:.3f} m/s w={state.v_angular:.3f} rad/s"
        )

        self.seq += 1

    def _write_csv(self, state: VehicleState, publish_dt_ms: Optional[float]) -> None:
        if self.csv_writer is None or self.csv_file is None:
            return

        self.csv_writer.writerow(
            [
                state.seq,
                state.robot_id,
                state.timestamp_ns,
                state.publish_time_ns,
                "" if publish_dt_ms is None else f"{publish_dt_ms:.3f}",
                f"{state.x:.6f}",
                f"{state.y:.6f}",
                f"{state.yaw:.6f}",
                f"{math.degrees(state.yaw):.6f}",
                f"{state.v_linear:.6f}",
                f"{state.v_angular:.6f}",
            ]
        )
        self.csv_file.flush()

    def _publish_mqtt(self, state: VehicleState) -> None:
        payload = json.dumps(state.to_dict())

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
    node = CompactOdomAdapter()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down CompactOdomAdapter")
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()