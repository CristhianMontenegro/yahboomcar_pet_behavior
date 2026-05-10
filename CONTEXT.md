# Contexto Del Proyecto Mascota ROSMASTER

## Objetivo General

Construir una mascota robot sobre ROSMASTER/Yahboom que pueda:

- moverse autonomamente;
- esquivar obstaculos;
- detectar personas con YOLO;
- saludar o interactuar;
- eventualmente tener emociones, estados, dialogo y LLM.

## Decision Actual

Primero se decidio hacer una V0 limpia, sin saludo ni LLM, para validar solo el piloto automatico.

La V0 usa el piloto automatico nativo de ROS/Yahboom:

- `yahboomcar_nav/launch/laser_bringup.launch`
- `yahboomcar_nav/launch/yahboomcar_navigation.launch`
- `map_server`
- `amcl`
- `move_base`
- `DWAPlannerROS`
- LiDAR por `/scan`

El paquete nuevo no reemplaza la navegacion nativa. Solo agrega un monitor pasivo.

## Estado Actual Del Codigo

Paquete creado:

```text
yahboomcar_ws/src/yahboomcar_pet_behavior/
```

Archivos actuales:

```text
CMakeLists.txt
package.xml
README.md
CONTEXT.md
config/autopilot_base.yaml
launch/autopilot_base.launch
scripts/autopilot_monitor.py
```

La V1 de saludo fue retirada para dejar solo V0 limpia.

No existen actualmente:

```text
person_greeting_supervisor.py
person_greeting.launch
person_greeting.yaml
```

## Que Hace V0

`autopilot_base.launch` arranca:

```text
laser_bringup
yahboomcar_navigation
autopilot_monitor
```

`autopilot_monitor.py` observa:

```text
/move_base/status
/move_base/result
/move_base_simple/goal
/move_base/goal
/scan
/JoyState
```

Publica:

```text
/pet_behavior/autopilot_state
/pet_behavior/autopilot_event
```

No publica:

```text
/cmd_vel
/move_base/cancel
TargetAngle
Buzzer
```

Por lo tanto, el monitor no mueve el robot ni interfiere con la navegacion.

## Como Probar V0

En la Jetson:

```bash
cd ~/yahboomcar_ws
catkin_make
source devel/setup.bash
chmod +x src/yahboomcar_pet_behavior/scripts/autopilot_monitor.py
roslaunch yahboomcar_pet_behavior autopilot_base.launch map:=my_map
```

Para arrancar solo el monitor si la base/navegacion ya estan corriendo:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch \
  start_bringup:=false \
  start_navigation:=false
```

Ver estado:

```bash
rostopic echo /pet_behavior/autopilot_state
```

## Riesgo De Prueba

V0 usa `move_base` nativo. El robot se movera si se envia un goal desde RViz o desde un topic de navegacion.

Precauciones:

- probar primero con ruedas levantadas;
- tener joystick o forma de corte lista;
- enviar goals cortos;
- evitar escaleras, cables y personas cerca;
- verificar `/scan`, `/odom` y RViz antes de mover.

## Decisiones Pendientes

Hay dos modos posibles para la mascota:

### Entorno Conocido

Usar mapas guardados y puntos memorizados.

Futuro:

```text
waypoints.yaml
waypoint_manager.py
patrol_controller.py
```

Esto sirve para:

- ir a base;
- patrullar zonas;
- volver a un punto;
- recordar cocina/sala/puerta/etc.

Requiere escanear mapa si el entorno no coincide con `my_map`.

### Entorno Cambiante / Mascota Libre

Usar roaming reactivo sin mapa.

Futuro:

```text
free_roam.launch
free_roam.yaml
free_roam_controller.py
```

Esto sirve para:

- andar libre;
- esquivar obstaculos en tiempo real;
- no depender de mapas.

No sirve tan bien para ir a destinos especificos.

## Evolucion Recomendada

Plan de fases:

```text
V0: piloto automatico nativo + monitor pasivo
V0.5: waypoints o roaming reactivo, segun modo elegido
V1: conectar YOLO y detectar persona sin actuar
V1.1: si ve persona, pausar y saludar con regla fija
V2: estados de mascota: idle, navigating, greeting, manual, resting
V3: emociones, dialogo, memoria y LLM
```

## Integracion YOLO Futura

El usuario tiene un YOLO liviano instalado que ya entrega objetos detectados.

Pendiente confirmar:

```text
topic exacto
tipo de mensaje
campo de clase
campo de confianza
si publica "person" literalmente
```

V0 ya tiene hooks configurables en:

```text
config/autopilot_base.yaml
```

Parametros:

```yaml
enable_yolo_hooks: false
detection_topic: /DetectMsg
detection_msg_type: target_array
person_label: person
min_confidence: 0.55
```

Activar hook sin actuar:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch enable_yolo_hooks:=true
```

## Como Retomar

Cuando se continue la conversacion, leer este archivo primero:

```text
yahboomcar_ws/src/yahboomcar_pet_behavior/CONTEXT.md
```

La siguiente decision tecnica debe ser:

```text
seguir con navegacion por mapa y waypoints
o crear modo roaming libre sin mapa
```
