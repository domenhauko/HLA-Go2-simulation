#!/usr/bin/env python3

from __future__ import annotations

import math
import time
from dataclasses import dataclass, asdict
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles
from nav_msgs.msg import Odometry


def quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Convert quaternion to yaw angle in radians."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


@dataclass
class VehicleState:
    robot_id: str
    seq: int
    source_stamp_ns: int
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


class Go2OdomAdapter(Node):
    def __init__(self) -> None:
        super().__init__("go2_odom_adapter")

        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("robot_id", "go2")
        self.declare_parameter("publish_rate_hz", 10.0)
        self.declare_parameter("print_json_like", False)

        odom_topic = str(self.get_parameter("odom_topic").value)
        self.robot_id = str(self.get_parameter("robot_id").value)
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)
        self.print_json_like = bool(self.get_parameter("print_json_like").value)

        qos_profile = QoSPresetProfiles.SENSOR_DATA.value

        self.subscription = self.create_subscription(
            Odometry,
            odom_topic,
            self.odom_callback,
            qos_profile,
        )

        self.latest_odom: Optional[Odometry] = None
        self.latest_odom_recv_time_ns: Optional[int] = None
        self.last_source_stamp_ns: Optional[int] = None
        self.last_publish_time_ns: Optional[int] = None
        self.seq: int = 0
        self.received_odom_count: int = 0

        period = 1.0 / max(publish_rate_hz, 1e-6)
        self.timer = self.create_timer(period, self.publish_vehicle_state)

        self.get_logger().info(
            f"Started Go2OdomAdapter | "
            f"odom_topic={odom_topic} | robot_id={self.robot_id} | "
            f"publish_rate_hz={publish_rate_hz}"
        )

    def odom_callback(self, msg: Odometry) -> None:
        self.latest_odom = msg
        self.latest_odom_recv_time_ns = time.time_ns()
        self.received_odom_count += 1

    def build_vehicle_state(self, msg: Odometry) -> VehicleState:
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        lin = msg.twist.twist.linear
        ang = msg.twist.twist.angular

        source_stamp_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)
        publish_time_ns = time.time_ns()
        yaw = quat_to_yaw(ori.x, ori.y, ori.z, ori.w)

        return VehicleState(
            robot_id=self.robot_id,
            seq=self.seq,
            source_stamp_ns=source_stamp_ns,
            publish_time_ns=publish_time_ns,
            x=float(pos.x),
            y=float(pos.y),
            z=float(pos.z),
            qx=float(ori.x),
            qy=float(ori.y),
            qz=float(ori.z),
            qw=float(ori.w),
            yaw=float(yaw),
            v_linear_x=float(lin.x),
            v_linear_y=float(lin.y),
            v_linear_z=float(lin.z),
            v_angular_x=float(ang.x),
            v_angular_y=float(ang.y),
            v_angular_z=float(ang.z),
            frame_id=str(msg.header.frame_id),
            child_frame_id=str(msg.child_frame_id),
        )

    def publish_vehicle_state(self) -> None:
        if self.latest_odom is None:
            self.get_logger().warn("No /odom received yet")
            return

        state = self.build_vehicle_state(self.latest_odom)

        source_dt_ms = "n/a"
        if self.last_source_stamp_ns is not None:
            source_dt_ms = f"{(state.source_stamp_ns - self.last_source_stamp_ns) / 1e6:.2f}"

        publish_dt_ms = "n/a"
        if self.last_publish_time_ns is not None:
            publish_dt_ms = f"{(state.publish_time_ns - self.last_publish_time_ns) / 1e6:.2f}"

        self.last_source_stamp_ns = state.source_stamp_ns
        self.last_publish_time_ns = state.publish_time_ns

        if self.print_json_like:
            self.get_logger().info(str(asdict(state)))
        else:
            self.get_logger().info(
                f"[VehicleState seq={state.seq}] "
                f"id={state.robot_id} | "
                f"src_dt={source_dt_ms} ms | pub_dt={publish_dt_ms} ms | "
                f"pos=({state.x:.3f}, {state.y:.3f}, {state.z:.3f}) | "
                f"yaw={state.yaw:.3f} rad ({math.degrees(state.yaw):.1f} deg) | "
                f"v_lin=({state.v_linear_x:.3f}, {state.v_linear_y:.3f}, {state.v_linear_z:.3f}) | "
                f"v_ang=({state.v_angular_x:.3f}, {state.v_angular_y:.3f}, {state.v_angular_z:.3f}) | "
                f"frame={state.frame_id} -> {state.child_frame_id}"
            )

        self.seq += 1


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = Go2OdomAdapter()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down Go2OdomAdapter")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()