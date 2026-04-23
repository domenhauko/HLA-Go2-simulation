#!/usr/bin/env python3

from __future__ import annotations

import math
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


class OdomSubscriber(Node):
    def __init__(self) -> None:
        super().__init__("go2_odom_subscriber")

        qos_profile = QoSPresetProfiles.SENSOR_DATA.value

        self.subscription = self.create_subscription(
            Odometry,
            "/odom",
            self.odom_callback,
            qos_profile,
        )

        self.msg_count: int = 0
        self.last_stamp_ns: Optional[int] = None

        self.get_logger().info("Subscribed to /odom")

    def odom_callback(self, msg: Odometry) -> None:
        self.msg_count += 1

        stamp_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)

        dt_ms: Optional[float] = None
        if self.last_stamp_ns is not None:
            dt_ms = (stamp_ns - self.last_stamp_ns) / 1e6
        self.last_stamp_ns = stamp_ns

        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        lin = msg.twist.twist.linear
        ang = msg.twist.twist.angular

        yaw = quat_to_yaw(ori.x, ori.y, ori.z, ori.w)

        dt_text = "n/a" if dt_ms is None else f"{dt_ms:.2f} ms"

        self.get_logger().info(
            f"[#{self.msg_count}] "
            f"frame_id={msg.header.frame_id} child_frame_id={msg.child_frame_id} | "
            f"t={stamp_ns} ns | dt={dt_text} | "
            f"pos=({pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f}) | "
            f"quat=({ori.x:.4f}, {ori.y:.4f}, {ori.z:.4f}, {ori.w:.4f}) | "
            f"yaw={yaw:.3f} rad ({math.degrees(yaw):.1f} deg) | "
            f"lin=({lin.x:.3f}, {lin.y:.3f}, {lin.z:.3f}) m/s | "
            f"ang=({ang.x:.3f}, {ang.y:.3f}, {ang.z:.3f}) rad/s"
        )


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = OdomSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down /odom subscriber")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()