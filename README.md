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

## Prueba Basica

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

## Nota Sobre Mapas

El argumento `map:=my_map` carga un mapa existente en `yahboomcar_nav/maps`.
Para navegacion real se debe usar un mapa creado en el entorno donde esta el
robot, por ejemplo:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch map:=casa
```

Ese comando deja el robot listo para recibir goals de navegacion, pero no inicia
una patrulla ni decide destinos automaticamente.
