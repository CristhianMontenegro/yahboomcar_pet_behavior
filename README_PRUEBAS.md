# README_PRUEBAS - Prueba Fisica Con LiDAR

Objetivo de manana: comprobar si el robot avanza usando `/robot/command` y,
si no avanza, aislar si el bloqueo viene de la compuerta frontal del LiDAR.

Orden recomendado:

```text
1. Preparar terminales ROS.
2. Probar movimiento normal con seguridad completa.
3. Si no avanza, revisar /robot/status y /robot/events.
4. Si sospechas LiDAR, hacer la prueba A/B.
5. Usar /cmd_vel directo solo al final para confirmar hardware/driver.
```

## Preparar Terminales

En cada terminal nueva donde uses `roslaunch`, `rostopic`, `rosnode`, `rosrun`
o `rosparam`, preparar primero el entorno:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
```

Si esas lineas ya estan en `~/.bashrc` y `rostopic list` funciona, no hace
falta repetirlas manualmente.

No necesitas ejecutar `roscore` aparte si usas `roslaunch`; `roslaunch` lo
arranca automaticamente si no hay master ROS activo.

Antes de mover:

- bateria cargada;
- espacio libre al frente del robot;
- mano lista para levantar el robot o cortar movimiento;
- no usar `/cmd_vel` directo salvo en el diagnostico final.

## Prueba 1 - Movimiento Seguro Normal

Esta es la primera prueba. Usa la seguridad completa, incluyendo LiDAR.

Terminal A, levantar la capa completa:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
roslaunch yahboomcar_pet_behavior pet_robot.launch
```

Si la base no reporta bateria real en `/voltage` o `/vel_raw` queda siempre en
cero, primero cerrar launches duplicados y relanzar limpio. Como diagnostico
de motores se puede probar sin LiDAR:

```bash
roslaunch yahboomcar_pet_behavior pet_robot.launch start_lidar:=false
```

En esta Yahboom X3 Plus la Rosmaster responde por una ruta serial estable de
`/dev/serial/by-path/...2.4.2...`; el launch la configura en el bringup. Evitar
dejar dos `pet_robot.launch` vivos a la vez porque ROS reemplaza nodos con el
mismo nombre.

Terminal B, ver telemetria:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
rostopic echo /robot/status
```

Terminal C, ver eventos:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
rostopic echo /robot/events
```

Terminal D, limpiar estado y poner modo backend:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
rostopic pub -1 /robot/emergency_stop std_msgs/Bool "data: false"
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"set_mode\",\"mode\":\"backend_controlled\",\"source\":\"physical_test\"}'"
```

Antes de mover, confirmar en `/robot/status`:

```text
emergency_stop: false
joy_active: false
mode: "backend_controlled"
```

Idealmente tambien:

```text
front_blocked: false
```

Enviar avance:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"move_forward\",\"speed\":0.10,\"duration\":1.0,\"source\":\"physical_test\"}'"
```

Resultado esperado:

```text
/robot/events muestra command_accepted
commanded_velocity.linear_x sube cerca de 0.16
raw_velocity.linear_x cambia si la base reporta movimiento
last_stop_reason termina como command_duration_elapsed
```

Nota: aunque el comando de prueba pida `speed: 0.10`, el controlador eleva el
avance no cero a `min_effective_linear_x` para superar la zona muerta de los
motores. El valor esta en `config/robot_control.yaml`.

Parar explicitamente:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"stop\",\"source\":\"physical_test\"}'"
```

## Si No Avanza

Revisar en `/robot/status` y `/robot/events`:

```text
emergency_stop
joy_active
mode
front_blocked
front_range
front_obstacle_range
front_blocked_points
front_blocked_angle_deg
front_valid_points
last_error
last_stop_reason
commanded_velocity
raw_velocity
```

Interpretacion rapida:

```text
last_error: "emergency_stop_active"
  limpiar /robot/emergency_stop.

last_error: "manual_control_active"
mode: "manual"
joy_active: true
  volver a backend_controlled y revisar joystick.

last_stop_reason: "front_obstacle_blocked"
front_blocked: true
  sospecha de LiDAR/compuerta frontal.

commanded_velocity cambia pero raw_velocity no
  el controlador publico, pero la base no reporto movimiento real.
```

Si `front_blocked` aparece `true`, o si el robot no avanza y quieres separar
LiDAR de otros bloqueos, hacer la Prueba 2.

## Prueba 2 - A/B Para Aislar LiDAR

Esta prueba compara el mismo comando con una sola diferencia:

```text
A: Prueba 1, seguridad normal, LiDAR bloquea avance si detecta obstaculo.
B: repetir el mismo comando, pero con front_obstacle_blocks_forward:=false.
```

La Prueba 1 ya es la Prueba A. Antes de cambiar nada, anotar:

```text
Avanzo fisicamente?
front_blocked
last_stop_reason
commanded_velocity
raw_velocity
```

Despues de anotar eso, detener el launch normal en Terminal A con `Ctrl+C`.

### Prueba B - Bloqueo Frontal Apagado Temporalmente

Levantar el mismo launch, pero apagando solo la compuerta frontal:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
roslaunch yahboomcar_pet_behavior pet_robot.launch front_obstacle_blocks_forward:=false
```

En Terminal D, repetir el mismo comando:

Detener:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"stop\",\"source\":\"lidar_ab_test\"}'"
```

```bash
rostopic pub -1 /robot/emergency_stop std_msgs/Bool "data: false"
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"set_mode\",\"mode\":\"backend_controlled\",\"source\":\"lidar_ab_test\"}'"
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"move_forward\",\"speed\":0.10,\"duration\":1.0,\"source\":\"lidar_ab_test\"}'"
```

En caso de no tener resultados con ambas pruebas revisar mode, joy_active,emergency_stop, commanded_velocity y raw_velocity.
