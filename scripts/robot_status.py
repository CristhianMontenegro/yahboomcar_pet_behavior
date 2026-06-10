#!/usr/bin/env python3
# encoding: utf-8
"""
Archivo: robot_status.py

Proposito general:
    Nodo de telemetria central del robot mascota. Junta estado del monitor,
    controlador, odometria, velocidad real, bateria, IMU, LiDAR y TF en un
    solo mensaje JSON facil de consumir por backend, UI o pruebas.

Entradas ROS principales:
    /robot/controller_state, /pet_behavior/autopilot_state, /cmd_vel,
    /vel_raw, /odom_raw, /odom, /voltage, /imu/data_raw, /imu/imu_raw,
    /imu/imu_data, /scan y /JoyState.

Salida ROS:
    /robot/status como std_msgs/String con JSON.

Informacion util:
    Los campos *_active indican si un topic fue visto recientemente. Un valor
    false no siempre es error: puede significar que el robot fisico no esta
    conectado o que ese sensor no esta publicado en la prueba actual.
"""
import json
import math

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Bool, Float32, String

try:
    import tf
except ImportError:
    tf = None


class RobotStatus:
    """Publicador central de telemetria JSON para la capa mascota."""

    def __init__(self):
        rospy.init_node("robot_status", anonymous=False)
        self.load_params()

        self.last_seen = {}
        self.autopilot_state = {}
        self.controller_state = {}
        self.cmd_vel = None
        self.vel_raw = None
        self.odom_raw = None
        self.odom = None
        self.voltage = None
        self.imu_raw = None
        self.imu_filtered = None
        self.joy_active = False
        self.scan_min_front = None

        self.tf_listener = tf.TransformListener() if tf else None
        self.status_pub = rospy.Publisher(self.robot_status_topic, String, queue_size=5)

        rospy.Subscriber(self.autopilot_state_topic, String, self.autopilot_state_callback, queue_size=5)
        rospy.Subscriber(self.controller_state_topic, String, self.controller_state_callback, queue_size=5)
        rospy.Subscriber(self.cmd_vel_topic, Twist, self.cmd_vel_callback, queue_size=5)
        rospy.Subscriber(self.vel_raw_topic, Twist, self.vel_raw_callback, queue_size=5)
        rospy.Subscriber(self.odom_raw_topic, Odometry, self.odom_raw_callback, queue_size=5)
        rospy.Subscriber(self.odom_topic, Odometry, self.odom_callback, queue_size=5)
        rospy.Subscriber(self.voltage_topic, Float32, self.voltage_callback, queue_size=5)
        rospy.Subscriber(self.imu_raw_topic, Imu, self.imu_raw_callback, queue_size=5)
        rospy.Subscriber(self.imu_alt_raw_topic, Imu, self.imu_alt_raw_callback, queue_size=5)
        rospy.Subscriber(self.imu_filtered_topic, Imu, self.imu_filtered_callback, queue_size=5)
        rospy.Subscriber(self.scan_topic, LaserScan, self.scan_callback, queue_size=1)
        rospy.Subscriber(self.joy_topic, Bool, self.joy_callback, queue_size=1)

        rospy.loginfo("robot_status ready. publishing %s", self.robot_status_topic)

    def load_params(self):
        self.robot_status_topic = rospy.get_param("~robot_status_topic", "/robot/status")
        self.autopilot_state_topic = rospy.get_param("~autopilot_state_topic", "/pet_behavior/autopilot_state")
        self.controller_state_topic = rospy.get_param("~controller_state_topic", "/robot/controller_state")
        self.cmd_vel_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")
        self.vel_raw_topic = rospy.get_param("~vel_raw_topic", "/vel_raw")
        self.odom_raw_topic = rospy.get_param("~odom_raw_topic", "/odom_raw")
        self.odom_topic = rospy.get_param("~odom_topic", "/odom")
        self.voltage_topic = rospy.get_param("~voltage_topic", "/voltage")
        self.imu_raw_topic = rospy.get_param("~imu_raw_topic", "/imu/data_raw")
        self.imu_alt_raw_topic = rospy.get_param("~imu_alt_raw_topic", "/imu/imu_raw")
        self.imu_filtered_topic = rospy.get_param("~imu_filtered_topic", "/imu/imu_data")
        self.scan_topic = rospy.get_param("~scan_topic", "/scan")
        self.joy_topic = rospy.get_param("~joy_topic", "/JoyState")

        self.publish_rate = float(rospy.get_param("~status_publish_rate", 2.0))
        self.topic_fresh_timeout = float(rospy.get_param("~topic_fresh_timeout", 2.0))
        self.front_angle_deg = float(rospy.get_param("~front_angle_deg", 25.0))
        self.tf_checks = rospy.get_param("~tf_checks", [
            {"parent": "odom", "child": "base_footprint"},
            {"parent": "base_link", "child": "laser"},
            {"parent": "laser_link", "child": "laser"},
        ])

    def remember(self, key):
        self.last_seen[key] = rospy.get_time()

    def autopilot_state_callback(self, msg):
        payload = self.parse_json(msg.data, "autopilot_state")
        if payload is not None:
            self.autopilot_state = payload
            self.remember("autopilot_state")

    def controller_state_callback(self, msg):
        payload = self.parse_json(msg.data, "controller_state")
        if payload is not None:
            self.controller_state = payload
            self.remember("controller_state")

    def cmd_vel_callback(self, msg):
        self.cmd_vel = self.twist_to_dict(msg)
        self.remember("cmd_vel")

    def vel_raw_callback(self, msg):
        self.vel_raw = self.twist_to_dict(msg)
        self.remember("vel_raw")

    def odom_raw_callback(self, msg):
        self.odom_raw = self.odom_to_dict(msg)
        self.remember("odom_raw")

    def odom_callback(self, msg):
        self.odom = self.odom_to_dict(msg)
        self.remember("odom")

    def voltage_callback(self, msg):
        self.voltage = float(msg.data)
        self.remember("voltage")

    def imu_raw_callback(self, msg):
        self.imu_raw = self.imu_to_dict(msg)
        self.remember("imu_raw")

    def imu_alt_raw_callback(self, msg):
        self.imu_raw = self.imu_to_dict(msg)
        self.remember("imu_alt_raw")

    def imu_filtered_callback(self, msg):
        self.imu_filtered = self.imu_to_dict(msg)
        self.remember("imu_filtered")

    def scan_callback(self, msg):
        max_angle = math.radians(self.front_angle_deg)
        valid_ranges = []
        for i, distance in enumerate(msg.ranges):
            angle = msg.angle_min + msg.angle_increment * i
            if abs(angle) <= max_angle and msg.range_min <= distance <= msg.range_max:
                valid_ranges.append(distance)
        self.scan_min_front = min(valid_ranges) if valid_ranges else None
        self.remember("scan")

    def joy_callback(self, msg):
        self.joy_active = bool(msg.data)
        self.remember("joy")

    def parse_json(self, raw, name):
        try:
            payload = json.loads(raw)
        except ValueError:
            rospy.logwarn_throttle(5.0, "Invalid %s JSON", name)
            return None
        return payload if isinstance(payload, dict) else None

    def fresh(self, key):
        stamp = self.last_seen.get(key)
        return stamp is not None and (rospy.get_time() - stamp) <= self.topic_fresh_timeout

    def status_payload(self):
        controller = self.controller_state
        autopilot = self.autopilot_state
        imu_raw_active = self.fresh("imu_raw") or self.fresh("imu_alt_raw")

        return {
            "stamp": rospy.get_time(),
            "state": controller.get("state", autopilot.get("mode", "unknown")),
            "mode": controller.get("mode", autopilot.get("mode", "unknown")),
            "emergency_stop": controller.get("emergency_stop", False),
            "joy_active": controller.get("joy_active", self.joy_active),
            "front_blocked": controller.get("front_blocked", autopilot.get("front_blocked")),
            "front_range": controller.get("front_range", autopilot.get("front_range", self.scan_min_front)),
            "front_obstacle_range": controller.get("front_obstacle_range", autopilot.get("front_obstacle_range")),
            "front_blocked_points": controller.get("front_blocked_points", autopilot.get("front_blocked_points")),
            "front_blocked_angle_deg": controller.get(
                "front_blocked_angle_deg",
                autopilot.get("front_blocked_angle_deg"),
            ),
            "front_valid_points": autopilot.get("front_valid_points"),
            "last_command": controller.get("last_command"),
            "last_source": controller.get("last_source"),
            "last_error": controller.get("last_error"),
            "last_stop_reason": controller.get("last_stop_reason"),
            "topics": {
                "autopilot_state_active": self.fresh("autopilot_state"),
                "controller_state_active": self.fresh("controller_state"),
                "cmd_vel_active": self.fresh("cmd_vel"),
                "vel_raw_active": self.fresh("vel_raw"),
                "odom_raw_active": self.fresh("odom_raw"),
                "odom_active": self.fresh("odom"),
                "lidar_active": self.fresh("scan"),
                "voltage_active": self.fresh("voltage"),
                "imu_raw_active": imu_raw_active,
                "imu_filtered_active": self.fresh("imu_filtered"),
            },
            "commanded_velocity": self.cmd_vel,
            "raw_velocity": self.vel_raw,
            "odom_raw": self.odom_raw,
            "odom": self.odom,
            "battery_voltage": self.voltage,
            "imu_raw": self.imu_raw,
            "imu_filtered": self.imu_filtered,
            "tf": self.tf_status(),
        }

    def spin(self):
        rate = rospy.Rate(self.publish_rate)
        while not rospy.is_shutdown():
            self.status_pub.publish(String(json.dumps(self.status_payload(), sort_keys=True)))
            rate.sleep()

    def tf_status(self):
        if not self.tf_listener:
            return {"available": False, "checks": []}

        checks = []
        for item in self.tf_checks:
            parent = item.get("parent") if isinstance(item, dict) else None
            child = item.get("child") if isinstance(item, dict) else None
            if not parent or not child:
                continue
            ok = False
            error = None
            try:
                self.tf_listener.lookupTransform(parent, child, rospy.Time(0))
                ok = True
            except Exception as exc:
                error = str(exc)
            checks.append({
                "parent": parent,
                "child": child,
                "ok": ok,
                "error": error,
            })
        return {"available": True, "checks": checks}

    def twist_to_dict(self, msg):
        return {
            "linear_x": msg.linear.x,
            "linear_y": msg.linear.y,
            "linear_z": msg.linear.z,
            "angular_x": msg.angular.x,
            "angular_y": msg.angular.y,
            "angular_z": msg.angular.z,
        }

    def odom_to_dict(self, msg):
        pose = msg.pose.pose
        twist = msg.twist.twist
        return {
            "frame_id": msg.header.frame_id,
            "child_frame_id": msg.child_frame_id,
            "position": {
                "x": pose.position.x,
                "y": pose.position.y,
                "z": pose.position.z,
            },
            "orientation": {
                "x": pose.orientation.x,
                "y": pose.orientation.y,
                "z": pose.orientation.z,
                "w": pose.orientation.w,
            },
            "twist": self.twist_to_dict(twist),
        }

    def imu_to_dict(self, msg):
        return {
            "frame_id": msg.header.frame_id,
            "linear_acceleration": {
                "x": msg.linear_acceleration.x,
                "y": msg.linear_acceleration.y,
                "z": msg.linear_acceleration.z,
            },
            "angular_velocity": {
                "x": msg.angular_velocity.x,
                "y": msg.angular_velocity.y,
                "z": msg.angular_velocity.z,
            },
            "orientation": {
                "x": msg.orientation.x,
                "y": msg.orientation.y,
                "z": msg.orientation.z,
                "w": msg.orientation.w,
            },
        }


if __name__ == "__main__":
    RobotStatus().spin()
