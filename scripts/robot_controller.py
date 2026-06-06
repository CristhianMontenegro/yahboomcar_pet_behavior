#!/usr/bin/env python3
# encoding: utf-8
"""
Archivo: robot_controller.py

Proposito general:
    Nodo principal de control seguro. Recibe ordenes
    de alto nivel, valida limites y publica velocidad solo si las condiciones
    de seguridad lo permiten.

Entradas ROS principales:
    /robot/command con JSON en std_msgs/String, /robot/cmd_vel_safe con Twist,
    /robot/mode, /robot/emergency_stop, /pet_behavior/autopilot_state y
    /JoyState.

Salidas ROS:
    /cmd_vel hacia el driver, /robot/controller_state para estado interno y
    /robot/events para auditoria de comandos, rechazos y paradas.

Informacion util:
    Backend, LLM o UI no deberian publicar directo a /cmd_vel. Este nodo es la
    compuerta unica para watchdog, emergency stop, limites de velocidad,
    bloqueo por obstaculo frontal y modo manual/autonomo.
"""
import json
import math

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String


class RobotController:
    """Compuerta segura para comandos de movimiento de la capa mascota."""

    def __init__(self):
        rospy.init_node("robot_controller", anonymous=False)
        self.load_params()

        self.mode = self.default_mode
        self.emergency_stop = False
        self.joy_active = False
        self.front_blocked = False
        self.front_range = None
        self.last_autopilot_state = {}

        self.active_control = False
        self.active_twist = Twist()
        self.last_output = Twist()
        self.last_command = "stop"
        self.last_source = None
        self.last_error = None
        self.last_stop_reason = "startup"
        self.last_command_time = 0.0
        self.command_until = 0.0
        self.force_stop_until = rospy.get_time() + self.stop_publish_duration

        self.cmd_pub = rospy.Publisher(self.cmd_vel_topic, Twist, queue_size=5)
        self.state_pub = rospy.Publisher(self.controller_state_topic, String, queue_size=5)
        self.event_pub = rospy.Publisher(self.controller_event_topic, String, queue_size=10)

        rospy.Subscriber(self.command_topic, String, self.command_callback, queue_size=10)
        rospy.Subscriber(self.direct_twist_topic, Twist, self.direct_twist_callback, queue_size=5)
        rospy.Subscriber(self.mode_topic, String, self.mode_callback, queue_size=5)
        rospy.Subscriber(self.emergency_stop_topic, Bool, self.emergency_stop_callback, queue_size=5)
        rospy.Subscriber(self.autopilot_state_topic, String, self.autopilot_state_callback, queue_size=5)
        rospy.Subscriber(self.joy_topic, Bool, self.joy_callback, queue_size=1)

        rospy.on_shutdown(self.on_shutdown)
        rospy.loginfo("robot_controller ready. command=%s output=%s", self.command_topic, self.cmd_vel_topic)
        self.publish_event("controller_ready", {
            "command_topic": self.command_topic,
            "cmd_vel_topic": self.cmd_vel_topic,
        })

    def load_params(self):
        self.cmd_vel_topic = rospy.get_param("~cmd_vel_topic", "/cmd_vel")
        self.command_topic = rospy.get_param("~command_topic", "/robot/command")
        self.direct_twist_topic = rospy.get_param("~direct_twist_topic", "/robot/cmd_vel_safe")
        self.mode_topic = rospy.get_param("~mode_topic", "/robot/mode")
        self.emergency_stop_topic = rospy.get_param("~emergency_stop_topic", "/robot/emergency_stop")
        self.autopilot_state_topic = rospy.get_param("~autopilot_state_topic", "/pet_behavior/autopilot_state")
        self.joy_topic = rospy.get_param("~joy_topic", "/JoyState")
        self.controller_state_topic = rospy.get_param("~controller_state_topic", "/robot/controller_state")
        self.controller_event_topic = rospy.get_param("~controller_event_topic", "/robot/events")

        self.default_mode = rospy.get_param("~default_mode", "idle")
        self.publish_rate = float(rospy.get_param("~controller_publish_rate", 10.0))
        self.default_command_duration = float(rospy.get_param("~default_command_duration", 0.6))
        self.max_command_duration = float(rospy.get_param("~max_command_duration", 3.0))
        self.watchdog_timeout = float(rospy.get_param("~watchdog_timeout", 1.5))
        self.stop_publish_duration = float(rospy.get_param("~stop_publish_duration", 0.6))

        self.max_linear_x = abs(float(rospy.get_param("~max_linear_x", 0.18)))
        self.max_linear_y = abs(float(rospy.get_param("~max_linear_y", 0.0)))
        self.max_angular_z = abs(float(rospy.get_param("~max_angular_z", 0.7)))
        self.default_linear_speed = abs(float(rospy.get_param("~default_linear_speed", 0.12)))
        self.default_turn_speed = abs(float(rospy.get_param("~default_turn_speed", 0.45)))

        self.front_obstacle_blocks_forward = bool(rospy.get_param("~front_obstacle_blocks_forward", True))
        self.manual_blocks_commands = bool(rospy.get_param("~manual_blocks_commands", True))

    def command_callback(self, msg):
        try:
            payload = json.loads(msg.data)
        except ValueError:
            self.reject_command("invalid_json", {"raw": msg.data})
            return

        if not isinstance(payload, dict):
            self.reject_command("command_payload_must_be_object", {"payload": payload})
            return

        command = str(payload.get("command", payload.get("action", ""))).strip().lower()
        source = str(payload.get("source", "unknown")).strip() or "unknown"

        if not command:
            self.reject_command("missing_command", payload)
            return

        if command in ("set_mode", "mode"):
            self.set_mode(str(payload.get("mode", "")).strip().lower(), source)
            return

        if command in ("emergency_stop", "estop"):
            active = bool(payload.get("active", True))
            self.set_emergency_stop(active, source)
            return

        if command in ("clear_emergency_stop", "reset_emergency", "reset_estop"):
            self.set_emergency_stop(False, source)
            return

        if command in ("stop", "halt"):
            self.stop("command_stop", command, source)
            return

        if self.emergency_stop:
            self.reject_command("emergency_stop_active", payload)
            return

        if self.manual_blocks_commands and (self.mode == "manual" or self.joy_active):
            self.reject_command("manual_control_active", payload)
            return

        twist = self.twist_from_command(command, payload)
        if twist is None:
            self.reject_command("unsupported_command", payload)
            return

        duration = self.duration_from_payload(payload)
        self.activate_twist(twist, duration, command, source)

    def direct_twist_callback(self, msg):
        if self.emergency_stop:
            self.reject_command("emergency_stop_active", {"source": self.direct_twist_topic})
            return
        if self.manual_blocks_commands and (self.mode == "manual" or self.joy_active):
            self.reject_command("manual_control_active", {"source": self.direct_twist_topic})
            return
        twist = self.clamp_twist(msg)
        self.activate_twist(twist, self.default_command_duration, "direct_twist", self.direct_twist_topic)

    def mode_callback(self, msg):
        mode = msg.data.strip().lower()
        try:
            payload = json.loads(msg.data)
            if isinstance(payload, dict):
                mode = str(payload.get("mode", mode)).strip().lower()
        except ValueError:
            pass
        self.set_mode(mode, self.mode_topic)

    def emergency_stop_callback(self, msg):
        self.set_emergency_stop(bool(msg.data), self.emergency_stop_topic)

    def autopilot_state_callback(self, msg):
        try:
            payload = json.loads(msg.data)
        except ValueError:
            rospy.logwarn_throttle(5.0, "Invalid autopilot state JSON")
            return
        if not isinstance(payload, dict):
            return
        self.last_autopilot_state = payload
        self.front_blocked = bool(payload.get("front_blocked", False))
        self.front_range = payload.get("front_range")

    def joy_callback(self, msg):
        self.joy_active = bool(msg.data)
        if self.joy_active and self.manual_blocks_commands:
            self.mode = "manual"
            if self.active_control:
                self.stop("manual_control_active", "manual_override", self.joy_topic)

    def set_mode(self, mode, source):
        allowed = ("idle", "manual", "autonomous", "backend_controlled")
        if mode not in allowed:
            self.reject_command("unsupported_mode", {"mode": mode, "allowed": allowed})
            return
        old_mode = self.mode
        self.mode = mode
        if mode in ("idle", "manual"):
            self.stop("mode_" + mode, "set_mode", source)
        self.publish_event("mode_changed", {"old_mode": old_mode, "mode": mode, "source": source})

    def set_emergency_stop(self, active, source):
        self.emergency_stop = bool(active)
        if self.emergency_stop:
            self.mode = "manual"
            self.stop("emergency_stop", "emergency_stop", source, hold=True)
        else:
            self.force_stop_until = rospy.get_time() + self.stop_publish_duration
            self.last_stop_reason = "emergency_stop_cleared"
        self.publish_event("emergency_stop", {"active": self.emergency_stop, "source": source})

    def activate_twist(self, twist, duration, command, source):
        if self.mode == "idle":
            self.mode = "backend_controlled"
        self.active_twist = self.clamp_twist(twist)
        self.active_control = True
        self.last_command = command
        self.last_source = source
        self.last_error = None
        self.last_stop_reason = None
        self.last_command_time = rospy.get_time()
        self.command_until = self.last_command_time + duration
        self.publish_event("command_accepted", {
            "command": command,
            "source": source,
            "duration": duration,
            "twist": self.twist_to_dict(self.active_twist),
        })

    def reject_command(self, reason, data):
        self.last_error = reason
        self.publish_event("command_rejected", {"reason": reason, "data": data})
        rospy.logwarn("robot command rejected: %s", reason)

    def stop(self, reason, command="stop", source="internal", hold=False):
        self.active_control = False
        self.active_twist = Twist()
        self.last_command = command
        self.last_source = source
        self.last_stop_reason = reason
        self.force_stop_until = rospy.get_time() + (self.watchdog_timeout if hold else self.stop_publish_duration)
        self.publish_event("robot_stop", {"reason": reason, "command": command, "source": source})

    def twist_from_command(self, command, payload):
        twist = Twist()
        if command == "move":
            linear = payload.get("linear", payload.get("linear_x", payload.get("x", 0.0)))
            angular = payload.get("angular", payload.get("angular_z", payload.get("z", 0.0)))
            if isinstance(linear, dict):
                twist.linear.x = self.extract_axis(linear, "x")
                twist.linear.y = self.extract_axis(linear, "y")
            else:
                twist.linear.x = self.safe_float(linear, 0.0)
                twist.linear.y = self.safe_float(payload.get("linear_y", payload.get("y", 0.0)), 0.0)
            twist.angular.z = self.extract_axis(angular, "z") if isinstance(angular, dict) else self.safe_float(angular, 0.0)
            return twist

        speed = abs(self.safe_float(payload.get("speed", payload.get("linear_speed", self.default_linear_speed)),
                                    self.default_linear_speed))
        turn = abs(self.safe_float(payload.get("angular", payload.get("turn_speed", self.default_turn_speed)),
                                   self.default_turn_speed))

        if command in ("move_forward", "forward", "advance"):
            twist.linear.x = speed
        elif command in ("move_backward", "backward", "reverse"):
            twist.linear.x = -speed
        elif command in ("turn_left", "left"):
            twist.angular.z = turn
        elif command in ("turn_right", "right"):
            twist.angular.z = -turn
        else:
            return None
        return twist

    def extract_axis(self, value, axis):
        if isinstance(value, dict):
            value = value.get(axis, 0.0)
        return self.safe_float(value, 0.0)

    def safe_float(self, value, fallback):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = fallback
        return value if math.isfinite(value) else fallback

    def duration_from_payload(self, payload):
        if "duration_ms" in payload:
            duration = self.safe_float(payload["duration_ms"], self.default_command_duration * 1000.0) / 1000.0
        else:
            duration = self.safe_float(
                payload.get("duration", payload.get("duration_s", self.default_command_duration)),
                self.default_command_duration,
            )
        if not math.isfinite(duration) or duration <= 0:
            duration = self.default_command_duration
        return max(0.05, min(duration, self.max_command_duration))

    def clamp_twist(self, twist):
        output = Twist()
        output.linear.x = self.clamp_axis(twist.linear.x, self.max_linear_x)
        output.linear.y = self.clamp_axis(twist.linear.y, self.max_linear_y)
        output.angular.z = self.clamp_axis(twist.angular.z, self.max_angular_z)
        return output

    def clamp_axis(self, value, limit):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        if not math.isfinite(value) or limit <= 0.0:
            return 0.0
        return max(-limit, min(limit, value))

    def compute_output(self):
        now = rospy.get_time()

        if self.emergency_stop:
            self.last_stop_reason = "emergency_stop"
            return Twist(), True

        if self.manual_blocks_commands and (self.mode == "manual" or self.joy_active):
            if self.active_control:
                self.stop("manual_control_active", "manual_override", self.joy_topic)
            return Twist(), now < self.force_stop_until

        if self.active_control:
            if now - self.last_command_time > self.watchdog_timeout:
                self.stop("watchdog_timeout", "watchdog", "controller")
                return Twist(), True
            if now > self.command_until:
                self.stop("command_duration_elapsed", "duration_elapsed", "controller")
                return Twist(), True
            if (
                self.front_obstacle_blocks_forward and
                self.front_blocked and
                self.active_twist.linear.x > 0.0
            ):
                self.stop("front_obstacle_blocked", "obstacle_guard", "autopilot_state")
                return Twist(), True
            return self.active_twist, True

        return Twist(), now < self.force_stop_until

    def state_payload(self, is_publishing):
        now = rospy.get_time()
        if self.emergency_stop:
            state = "emergency"
        elif self.active_control:
            state = "moving" if self.twist_has_motion(self.active_twist) else "stopped"
        elif self.last_stop_reason and self.last_stop_reason.startswith("front_obstacle"):
            state = "blocked"
        else:
            state = "idle"

        return {
            "state": state,
            "mode": self.mode,
            "emergency_stop": self.emergency_stop,
            "joy_active": self.joy_active,
            "front_blocked": self.front_blocked,
            "front_range": self.front_range,
            "active_control": self.active_control,
            "publishing_cmd_vel": is_publishing,
            "last_command": self.last_command,
            "last_source": self.last_source,
            "last_error": self.last_error,
            "last_stop_reason": self.last_stop_reason,
            "command_age": now - self.last_command_time if self.last_command_time else None,
            "command_expires_in": self.command_until - now if self.active_control else None,
            "output": self.twist_to_dict(self.last_output),
            "limits": {
                "max_linear_x": self.max_linear_x,
                "max_linear_y": self.max_linear_y,
                "max_angular_z": self.max_angular_z,
            },
        }

    def spin(self):
        rate = rospy.Rate(self.publish_rate)
        while not rospy.is_shutdown():
            output, should_publish = self.compute_output()
            self.last_output = output
            if should_publish:
                self.cmd_pub.publish(output)
            self.state_pub.publish(String(json.dumps(self.state_payload(should_publish), sort_keys=True)))
            rate.sleep()

    def on_shutdown(self):
        stop = Twist()
        for _ in range(3):
            self.cmd_pub.publish(stop)
            rospy.sleep(0.05)

    def publish_event(self, event, data):
        payload = {
            "stamp": rospy.get_time(),
            "event": event,
            "data": data,
        }
        self.event_pub.publish(String(json.dumps(payload, sort_keys=True)))

    def twist_has_motion(self, twist):
        return (
            abs(twist.linear.x) > 1e-4 or
            abs(twist.linear.y) > 1e-4 or
            abs(twist.angular.z) > 1e-4
        )

    def twist_to_dict(self, twist):
        return {
            "linear_x": twist.linear.x,
            "linear_y": twist.linear.y,
            "angular_z": twist.angular.z,
        }


if __name__ == "__main__":
    RobotController().spin()
