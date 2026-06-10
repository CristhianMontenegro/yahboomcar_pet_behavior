#!/usr/bin/env python3
# encoding: utf-8
"""
Archivo: autopilot_monitor.py

Proposito general:
    Nodo ROS pasivo que observa el contexto de navegacion del robot mascota.
    Resume estado de LiDAR, move_base, joystick y detecciones opcionales de
    YOLO, pero no mueve motores ni publica /cmd_vel.

Entradas ROS principales:
    /scan, /move_base_simple/goal, /move_base/goal, /move_base/status,
    /move_base/result, /JoyState y, si se activa, el topic de detecciones.

Salidas ROS:
    /pet_behavior/autopilot_state y /pet_behavior/autopilot_event como JSON
    dentro de std_msgs/String.

Informacion util:
    Este archivo alimenta al controlador y al backend con contexto seguro. Si
    se necesita cambiar movimiento fisico, hacerlo en robot_controller.py.
"""
import json
import math

import rospy
from actionlib_msgs.msg import GoalStatus, GoalStatusArray
from geometry_msgs.msg import PoseStamped
from move_base_msgs.msg import MoveBaseActionGoal, MoveBaseActionResult
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String
from yahboomcar_msgs.msg import TargetArray


class AutopilotMonitor:
    """Monitor pasivo V0 para el autopiloto existente basado en move_base."""

    def __init__(self):
        rospy.init_node("autopilot_monitor", anonymous=False)

        self.load_params()
        self.mode = "idle"
        self.joy_active = False
        self.last_goal = None
        self.last_result_status = None
        self.min_front_range = None
        self.front_valid_points = 0
        self.front_blocked_points = 0
        self.front_blocked_angle_deg = None
        self.last_detection = None

        self.state_pub = rospy.Publisher(self.state_topic, String, queue_size=5)
        self.event_pub = rospy.Publisher(self.event_topic, String, queue_size=10)

        rospy.Subscriber(self.scan_topic, LaserScan, self.scan_callback, queue_size=1)
        rospy.Subscriber(self.goal_topic, PoseStamped, self.simple_goal_callback, queue_size=1)
        rospy.Subscriber(self.move_base_goal_topic, MoveBaseActionGoal, self.move_base_goal_callback, queue_size=1)
        rospy.Subscriber(self.move_base_status_topic, GoalStatusArray, self.status_callback, queue_size=1)
        rospy.Subscriber(self.move_base_result_topic, MoveBaseActionResult, self.result_callback, queue_size=1)
        rospy.Subscriber(self.joy_topic, Bool, self.joy_callback, queue_size=1)

        if self.enable_yolo_hooks:
            self.setup_detection_hook()

        rospy.loginfo("autopilot_monitor ready. map=%s yolo_hooks=%s",
                      self.map_name, self.enable_yolo_hooks)

    def load_params(self):
        self.map_name = rospy.get_param("~map", rospy.get_param("~map_name", "my_map"))
        self.scan_topic = rospy.get_param("~scan_topic", "/scan")
        self.goal_topic = rospy.get_param("~goal_topic", "/move_base_simple/goal")
        self.move_base_goal_topic = rospy.get_param("~move_base_goal_topic", "/move_base/goal")
        self.move_base_status_topic = rospy.get_param("~move_base_status_topic", "/move_base/status")
        self.move_base_result_topic = rospy.get_param("~move_base_result_topic", "/move_base/result")
        self.joy_topic = rospy.get_param("~joy_topic", "/JoyState")
        self.front_angle_deg = float(rospy.get_param("~front_angle_deg", 25.0))
        self.front_obstacle_range = float(rospy.get_param("~front_obstacle_range", 0.35))
        self.front_obstacle_min_points = max(1, int(rospy.get_param("~front_obstacle_min_points", 1)))
        self.enable_yolo_hooks = bool(rospy.get_param("~enable_yolo_hooks", False))
        self.detection_topic = rospy.get_param("~detection_topic", "/DetectMsg")
        self.detection_msg_type = rospy.get_param("~detection_msg_type", "target_array")
        self.person_label = rospy.get_param("~person_label", "person")
        self.min_confidence = float(rospy.get_param("~min_confidence", 0.55))
        self.state_topic = rospy.get_param("~state_topic", "/pet_behavior/autopilot_state")
        self.event_topic = rospy.get_param("~event_topic", "/pet_behavior/autopilot_event")
        self.publish_rate = float(rospy.get_param("~publish_rate", 2.0))

    def setup_detection_hook(self):
        if self.detection_msg_type == "target_array":
            rospy.Subscriber(self.detection_topic, TargetArray, self.target_array_callback, queue_size=1)
        elif self.detection_msg_type == "json_string":
            rospy.Subscriber(self.detection_topic, String, self.json_detection_callback, queue_size=1)
        else:
            rospy.logwarn("Unsupported detection_msg_type=%s; YOLO hook disabled", self.detection_msg_type)

    def simple_goal_callback(self, msg):
        self.last_goal = self.pose_to_dict(msg)
        self.publish_event("goal_received", {"source": self.goal_topic, "goal": self.last_goal})

    def move_base_goal_callback(self, msg):
        self.last_goal = self.pose_to_dict(msg.goal.target_pose)
        self.publish_event("goal_received", {"source": self.move_base_goal_topic, "goal": self.last_goal})

    def status_callback(self, msg):
        active_states = (GoalStatus.PENDING, GoalStatus.ACTIVE, GoalStatus.PREEMPTING)
        if self.joy_active:
            self.mode = "manual"
        elif any(status.status in active_states for status in msg.status_list):
            self.mode = "navigating"
        else:
            self.mode = "idle"

    def result_callback(self, msg):
        self.last_result_status = int(msg.status.status)
        self.publish_event("navigation_result", {
            "status": self.last_result_status,
            "text": msg.status.text,
        })

    def joy_callback(self, msg):
        self.joy_active = bool(msg.data)
        if self.joy_active:
            self.mode = "manual"
            self.publish_event("manual_control", {"active": True})

    def scan_callback(self, msg):
        max_angle = math.radians(self.front_angle_deg)
        valid_ranges = []
        blocked_ranges = []
        for i, distance in enumerate(msg.ranges):
            angle = msg.angle_min + msg.angle_increment * i
            if abs(angle) <= max_angle and msg.range_min <= distance <= msg.range_max:
                angle_deg = math.degrees(angle)
                valid_ranges.append((distance, angle_deg))
                if distance < self.front_obstacle_range:
                    blocked_ranges.append((distance, angle_deg))

        self.front_valid_points = len(valid_ranges)
        self.front_blocked_points = len(blocked_ranges)
        if valid_ranges:
            closest = min(valid_ranges, key=lambda item: item[0])
            self.min_front_range = closest[0]
        else:
            self.min_front_range = None

        if blocked_ranges:
            closest_blocking = min(blocked_ranges, key=lambda item: item[0])
            self.front_blocked_angle_deg = closest_blocking[1]
        else:
            self.front_blocked_angle_deg = None

    def target_array_callback(self, msg):
        best = None
        for target in msg.data:
            label = str(target.frame_id).strip()
            confidence = float(target.scores)
            if best is None or confidence > best["confidence"]:
                best = {"label": label, "confidence": confidence}
        self.update_detection(best)

    def json_detection_callback(self, msg):
        try:
            payload = json.loads(msg.data)
        except ValueError:
            rospy.logwarn_throttle(5.0, "Invalid detection JSON")
            return

        if isinstance(payload, list):
            objects = payload
        elif isinstance(payload, dict):
            objects = payload.get("objects", [])
        else:
            objects = []

        best = None
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            label = str(obj.get("label", obj.get("class", obj.get("name", "")))).strip()
            confidence = float(obj.get("confidence", obj.get("score", 0.0)))
            if best is None or confidence > best["confidence"]:
                best = {"label": label, "confidence": confidence}
        self.update_detection(best)

    def update_detection(self, detection):
        self.last_detection = detection
        if detection and detection["label"] == self.person_label and detection["confidence"] >= self.min_confidence:
            self.publish_event("person_seen_hook", detection)

    def pose_to_dict(self, pose_msg):
        pose = pose_msg.pose
        return {
            "frame_id": pose_msg.header.frame_id,
            "x": pose.position.x,
            "y": pose.position.y,
            "z": pose.position.z,
            "oz": pose.orientation.z,
            "ow": pose.orientation.w,
        }

    def publish_event(self, event, data):
        payload = {"event": event, "data": data}
        self.event_pub.publish(String(json.dumps(payload)))
        rospy.loginfo("autopilot event: %s", payload)

    def state_payload(self):
        front_blocked = (
            self.min_front_range is not None and
            self.front_blocked_points >= self.front_obstacle_min_points
        )
        return {
            "mode": self.mode,
            "map": self.map_name,
            "joy_active": self.joy_active,
            "front_range": self.min_front_range,
            "front_blocked": front_blocked,
            "front_angle_deg": self.front_angle_deg,
            "front_obstacle_range": self.front_obstacle_range,
            "front_obstacle_min_points": self.front_obstacle_min_points,
            "front_valid_points": self.front_valid_points,
            "front_blocked_points": self.front_blocked_points,
            "front_blocked_angle_deg": self.front_blocked_angle_deg,
            "last_goal": self.last_goal,
            "last_result_status": self.last_result_status,
            "last_detection": self.last_detection,
            "yolo_hooks_enabled": self.enable_yolo_hooks,
        }

    def spin(self):
        rate = rospy.Rate(self.publish_rate)
        while not rospy.is_shutdown():
            self.state_pub.publish(String(json.dumps(self.state_payload())))
            rate.sleep()


if __name__ == "__main__":
    AutopilotMonitor().spin()
