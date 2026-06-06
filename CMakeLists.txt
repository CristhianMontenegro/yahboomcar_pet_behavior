# Archivo: CMakeLists.txt
#
# Proposito general:
#   Configuracion de compilacion Catkin del paquete yahboomcar_pet_behavior.
#   Declara dependencias ROS y registra los scripts Python para que roslaunch
#   pueda ejecutarlos como nodos instalables.
#
# Informacion util:
#   Si se agrega un nuevo nodo Python en scripts/, tambien debe agregarse en
#   catkin_install_python. Si el nodo importa nuevos mensajes ROS, agregar la
#   dependencia en find_package, catkin_package y package.xml.

cmake_minimum_required(VERSION 3.0.2)
project(yahboomcar_pet_behavior)

find_package(catkin REQUIRED COMPONENTS
  actionlib_msgs
  geometry_msgs
  move_base_msgs
  nav_msgs
  rospy
  sensor_msgs
  std_msgs
  tf
  yahboomcar_msgs
)

catkin_package(
  CATKIN_DEPENDS
    actionlib_msgs
    geometry_msgs
    move_base_msgs
    nav_msgs
    rospy
    sensor_msgs
    std_msgs
    tf
    yahboomcar_msgs
)

catkin_install_python(PROGRAMS
  scripts/autopilot_monitor.py
  scripts/robot_controller.py
  scripts/robot_status.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
