cmake_minimum_required(VERSION 3.0.2)
project(yahboomcar_pet_behavior)

find_package(catkin REQUIRED COMPONENTS
  actionlib_msgs
  geometry_msgs
  move_base_msgs
  rospy
  sensor_msgs
  std_msgs
  yahboomcar_msgs
)

catkin_package(
  CATKIN_DEPENDS
    actionlib_msgs
    geometry_msgs
    move_base_msgs
    rospy
    sensor_msgs
    std_msgs
    yahboomcar_msgs
)

catkin_install_python(PROGRAMS
  scripts/autopilot_monitor.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
