# yahboomcar_pet_behavior

Paquete ROS para construir una capa de comportamiento tipo mascota sobre el
ROSMASTER/Yahboom X3 Plus.

La version actual es una base minima: puede arrancar la base de navegacion
existente del robot y publicar estado de observacion, pero no toma decisiones ni
mueve el robot por si sola.

## Contenido

- `launch/autopilot_base.launch`: launch principal para iniciar bringup,
  navegacion nativa opcional y monitor.
- `config/autopilot_base.yaml`: parametros de topicos, mapa y observacion.
- `scripts/autopilot_monitor.py`: nodo pasivo que observa LiDAR, estado de
  `move_base`, goals, joystick y detecciones opcionales.

## Estado Actual

El monitor publica:

```text
/pet_behavior/autopilot_state
/pet_behavior/autopilot_event
```

No publica `/cmd_vel`, no cancela objetivos de navegacion y no controla el
brazo. Por eso es seguro como primera capa de observacion.

## Preparar La Terminal

En la Jetson:

```bash
cd ~/yahboomcar_ws
catkin_make
source devel/setup.bash
chmod +x src/yahboomcar_pet_behavior/scripts/autopilot_monitor.py
```

En cada terminal nueva que uses para ROS:

```bash
cd ~/yahboomcar_ws
source devel/setup.bash
```

## Pruebas Basicas

Monitor solamente:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch \
  start_bringup:=false \
  start_navigation:=false
```

Base, LiDAR y monitor sin navegacion por mapa:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch \
  start_navigation:=false
```

Observar el estado:

```bash
rostopic echo /pet_behavior/autopilot_state
```

## Siguiente Paso

Si estas pruebas funcionan, el siguiente avance recomendado es crear un modo
`free_roam` seguro sin mapa:

```text
config/free_roam.yaml
launch/free_roam.launch
scripts/free_roam_controller.py
```

Ese modo haria que el robot avance lento, use `/scan` para detectar obstaculos,
gire cuando el frente este bloqueado y se detenga si entra control manual.
