# README - yahboomcar_pet_behavior

## Encabezado Del Archivo

Este archivo documenta el estado actual de la Semana 1 del paquete
`yahboomcar_pet_behavior`, como probarlo paso a paso y que queda pendiente de
validar con el robot fisico.

Informacion util: el "main" recomendado de la capa mascota es
`launch/pet_robot.launch`. El nodo `autopilot_monitor.py` solo observa el
contexto; el nodo `robot_controller.py` es la unica pieza de esta capa que debe
publicar comandos seguros hacia `/cmd_vel`.

## Objetivo Del Paquete

Este paquete crea una capa de comportamiento tipo mascota sobre el
ROSMASTER/Yahboom X3 Plus.

La arquitectura actual separa tres responsabilidades:

- observacion pasiva del entorno y navegacion;
- control seguro de movimiento para comandos de alto nivel;
- telemetria central para backend, UI y pruebas.

## Estado Semana 1

Codigo listo:

- `pet_robot.launch`: launch principal de la capa mascota.
- `autopilot_monitor.py`: observa LiDAR, joystick, goals y estado de `move_base`.
- `robot_controller.py`: recibe comandos seguros y publica `/cmd_vel`.
- `robot_status.py`: publica telemetria central en `/robot/status`.
- `autopilot_base.yaml`: parametros del monitor pasivo.
- `robot_control.yaml`: limites, watchdog, topics y seguridad.

Seguridad implementada:

- parada de emergencia por `/robot/emergency_stop`;
- watchdog por perdida de comandos;
- limites de velocidad;
- duracion maxima de comandos;
- bloqueo de avance si `front_blocked=true`;
- modo manual bloquea comandos del backend;
- publicacion de velocidad cero al detenerse o cerrar el nodo.

Pendiente de validar con robot fisico:

- avance real;
- retroceso real;
- giro real izquierda/derecha;
- parada real despues de movimiento;
- cambio real en `/vel_raw`;
- cambio real en `/odom_raw`;
- voltaje real en `/voltage`;
- TF `odom -> base_footprint`;
- TF base/LiDAR;
- IMU real;
- calibracion de velocidades.

```

## Archivos Principales

- `launch/pet_robot.launch`: main ROS de la capa mascota.
- `launch/autopilot_base.launch`: launch solo para observacion/autopiloto.
- `scripts/autopilot_monitor.py`: monitor pasivo, no mueve motores.
- `scripts/robot_controller.py`: compuerta segura de movimiento.
- `scripts/robot_status.py`: telemetria central.
- `config/autopilot_base.yaml`: configuracion del monitor.
- `config/robot_control.yaml`: configuracion de control, seguridad y status.

## Topics Importantes

```text
/robot/command                 entrada segura de comandos JSON
/robot/cmd_vel_safe            entrada Twist segura para pruebas locales
/robot/emergency_stop          parada de emergencia
/robot/controller_state        estado interno del controlador
/robot/events                  eventos, rechazos y paradas
/robot/status                  telemetria central
/pet_behavior/autopilot_state  estado observado por el monitor
/pet_behavior/autopilot_event  eventos del monitor
/cmd_vel                       orden final hacia el driver/motores
/scan                          datos del LiDAR
/vel_raw                       velocidad real reportada por la base
/odom_raw                      odometria cruda
/voltage                       bateria
```

Importante: backend, LLM o UI deben mandar comandos a `/robot/command`, no
directo a `/cmd_vel`. Publicar directo en `/cmd_vel` salta watchdog, limites,
emergency stop y bloqueo por obstaculo.

## Preparar La Jetson

Terminal 1, levantar ROS core local:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
roscore
```

Cada terminal adicional que uses para comandos ROS:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_IP=127.0.0.1
cd ~/yahboomcar_ws
source devel/setup.bash
```

Compilar y dejar scripts ejecutables:

```bash
cd ~/yahboomcar_ws
catkin_make
source devel/setup.bash
chmod +x src/yahboomcar_pet_behavior/scripts/autopilot_monitor.py
chmod +x src/yahboomcar_pet_behavior/scripts/robot_controller.py
chmod +x src/yahboomcar_pet_behavior/scripts/robot_status.py
```



## Prueba 1 - Solo Codigo Sin Robot

Objetivo: comprobar que los nodos arrancan y que el controlador publica
comandos sin levantar driver, LiDAR ni base fisica.

Terminal adicional A:

```bash
roslaunch yahboomcar_pet_behavior pet_robot.launch start_bringup:=false
```

Terminal adicional B, revisar nodos:

```bash
rosnode list
```

Debes ver al menos:

```text
/autopilot_monitor
/robot_controller
/robot_status
```

Terminal adicional B, revisar topics:

```bash
rostopic list | grep robot
```

Debes ver topics como:

```text
/robot/command
/robot/controller_state
/robot/events
/robot/status
```

Terminal adicional B, observar telemetria:

```bash
rostopic echo /robot/status
```

Es normal que varios campos `*_active` salgan en `false`, porque no hay robot
fisico publicando sensores.

## Prueba 2 - Comando Seguro Sin Robot

Objetivo: verificar que `/robot/command` se traduce a `/cmd_vel`.

Terminal adicional B:

```bash
rostopic echo /cmd_vel
```

Terminal adicional C:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"move_forward\",\"speed\":0.10,\"duration\":0.5,\"source\":\"ghost_test\"}'"
```

Resultado esperado en `/cmd_vel`:

```text
linear.x: 0.1
angular.z: 0.0
```

Luego debe volver a velocidad cero cuando termina la duracion del comando.

Probar giro:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"turn_left\",\"angular\":0.45,\"duration\":0.5,\"source\":\"ghost_test\"}'"
```

Resultado esperado:

```text
linear.x: 0.0
angular.z: 0.45
```

## Prueba 3 - Emergency Stop

Objetivo: confirmar que la parada de emergencia fuerza velocidad cero.

Activar emergency stop:

```bash
rostopic pub -1 /robot/emergency_stop std_msgs/Bool "data: true"
```

Intentar mover:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"move_forward\",\"speed\":0.10,\"duration\":0.5,\"source\":\"ghost_test\"}'"
```

Resultado esperado:

- `/cmd_vel` queda en cero;
- `/robot/events` muestra rechazo por `emergency_stop_active`;
- `/robot/status` muestra `emergency_stop: true`.

Ver eventos:

```bash
rostopic echo /robot/events
```

Liberar emergency stop:

```bash
rostopic pub -1 /robot/emergency_stop std_msgs/Bool "data: false"
```

## Prueba 4 - Watchdog

Objetivo: confirmar que el robot se detiene si no se refrescan comandos.

Enviar un comando largo:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"move_forward\",\"speed\":0.10,\"duration\":3.0,\"source\":\"watchdog_test\"}'"
```

Resultado esperado:

- `/cmd_vel` publica avance al inicio;
- despues de aproximadamente `1.5` segundos, el watchdog publica cero;
- `/robot/events` muestra `watchdog_timeout`.

## Prueba 5 - Con Robot Fisico

Objetivo: validar que el codigo controla realmente la base.

Antes de probar movimiento:

- cargar bateria;
- dejar espacio libre alrededor;
- tener la mano lista para levantar/detener el robot;
- partir con velocidades bajas;
- no publicar directo a `/cmd_vel`.

Terminal adicional A:

```bash
roslaunch yahboomcar_pet_behavior pet_robot.launch
```

Terminal adicional B, revisar que el driver exista:

```bash
rosnode list | grep driver
```

Terminal adicional B, revisar suscripcion a `/cmd_vel`:

```bash
rostopic info /cmd_vel
```

Debe aparecer algun subscriber asociado al driver/base.

Terminal adicional B, observar telemetria:

```bash
rostopic echo /robot/status
```

Terminal adicional C, enviar avance corto:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"move_forward\",\"speed\":0.08,\"duration\":0.4,\"source\":\"physical_test\"}'"
```

Validar:

- el robot avanza fisicamente;
- `/cmd_vel` cambia;
- `/vel_raw` cambia;
- `/odom_raw` cambia;
- luego el robot se detiene.

Comando de parada:

```bash
rostopic pub -1 /robot/command std_msgs/String \
"data: '{\"command\":\"stop\",\"source\":\"physical_test\"}'"
```

Parada de emergencia:

```bash
rostopic pub -1 /robot/emergency_stop std_msgs/Bool "data: true"
```

## Prueba 6 - Telemetria Fisica

Con el robot encendido, revisar:

```bash
rostopic echo /vel_raw
rostopic echo /odom_raw
rostopic echo /voltage
rostopic echo /imu/imu_data
rostopic echo /scan
```

Revisar frecuencia:

```bash
rostopic hz /odom_raw
rostopic hz /scan
```

Revisar TF:

```bash
rosrun tf tf_echo odom base_footprint
rosrun tf tf_echo base_link laser
rosrun tf tf_echo laser_link laser
```

Nota: dependiendo del modelo/configuracion, puede existir `base_link -> laser`
o `laser_link -> laser`. Por eso `robot_status.py` revisa ambos casos.

## Comandos Soportados Por /robot/command

Avanzar:

```json
{"command":"move_forward","speed":0.10,"duration":0.5,"source":"backend"}
```

Retroceder:

```json
{"command":"move_backward","speed":0.10,"duration":0.5,"source":"backend"}
```

Girar izquierda:

```json
{"command":"turn_left","angular":0.45,"duration":0.5,"source":"backend"}
```

Girar derecha:

```json
{"command":"turn_right","angular":0.45,"duration":0.5,"source":"backend"}
```

Movimiento generico:

```json
{"command":"move","linear":{"x":0.10},"angular":{"z":0.0},"duration_ms":500,"source":"backend"}
```

Detener:

```json
{"command":"stop","source":"backend"}
```

Emergency stop:

```json
{"command":"emergency_stop","active":true,"source":"backend"}
```

Cambiar modo:

```json
{"command":"set_mode","mode":"backend_controlled","source":"backend"}
```

Modos soportados:

```text
idle
manual
autonomous
backend_controlled
```

## Checklist De Cierre Semana 1

Codigo:

-  launch principal de la capa mascota;
-  monitor pasivo;
-  controlador seguro;
-  telemetria central;
-  emergency stop;
-  watchdog;
-  limites de velocidad;
-  bloqueo por obstaculo frontal;
-  contrato para backend;
-  documentacion base.

Robot fisico:

- avanzar;
- retroceder;
- girar izquierda;
- girar derecha;
- detenerse despues de movimiento real;
- validar `/vel_raw`;
- validar `/odom_raw`;
- validar `/voltage`;
- validar IMU(Sensor de movimineto/orientacion);
- validar TF(Mapa de coordenadas entre partes del robot);
- validar emergency stop fisico;
- validar watchdog fisico.
