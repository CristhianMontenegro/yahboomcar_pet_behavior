# README - yahboomcar_pet_behavior

## Encabezado Del Archivo

Este archivo resume el estado actual de la Semana 1 del paquete
`yahboomcar_pet_behavior`. Las pruebas paso a paso estan separadas en
[`README_PRUEBAS.md`](README_PRUEBAS.md).

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

## Archivos Principales

- [`README_PRUEBAS.md`](README_PRUEBAS.md): guia operativa de arranque,
  pruebas y diagnostico.
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

## Pruebas Y Validacion

Las instrucciones operativas de arranque, pruebas sin robot, pruebas fisicas,
aislamiento de LiDAR y diagnostico de hardware estan en:

- [`README_PRUEBAS.md`](README_PRUEBAS.md)

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
