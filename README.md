# yahboomcar_pet_behavior V0

Version minima para arrancar la navegacion autonoma existente y observar su estado.

V0 no detecta personas, no saluda, no mueve el brazo y no toma decisiones. Solo deja una base limpia para validar que el piloto automatico funciona antes de conectar YOLO.

## Archivos

- `launch/autopilot_base.launch`: arranca `laser_bringup`, `yahboomcar_navigation` y el monitor.
- `config/autopilot_base.yaml`: parametros del mapa, topicos observados y nombres reservados para futura deteccion.
- `scripts/autopilot_monitor.py`: monitor pasivo. No publica `/cmd_vel` ni cancela objetivos.

## Uso

Arrancar piloto automatico completo:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch map:=my_map
```

Si ya tienes base y navegacion corriendo, arrancar solo el monitor:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch \
  start_bringup:=false \
  start_navigation:=false
```

## Estado Publicado

El monitor publica:

```text
/pet_behavior/autopilot_state
/pet_behavior/autopilot_event
```

`autopilot_state` incluye:

- `mode`: `idle`, `navigating` o `manual`
- `map`
- `joy_active`
- `front_range`
- `front_blocked`
- `last_goal`
- `last_result_status`
- `last_detection`
- `yolo_hooks_enabled`

## Hook Futuro De YOLO

V0 puede escuchar detecciones sin actuar sobre ellas:

```bash
roslaunch yahboomcar_pet_behavior autopilot_base.launch enable_yolo_hooks:=true
```

Esto solo publica eventos como `person_seen_hook`. El robot no se detiene ni saluda todavia.
