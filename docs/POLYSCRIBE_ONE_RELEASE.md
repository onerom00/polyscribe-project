# PolyScribe One: revisión y activación

Este cambio prepara persistencia estructurada y un adaptador para el proveedor
actual. No añade proveedores pagados ni procesamiento en segundo plano.

## Orden de activación

1. Revisar el PR y comprobar sus pruebas. Verificar en Render la rama conectada,
   auto-deploy, comandos efectivos y existencia de staging; `render.yaml` no
   demuestra la configuración efectiva de un servicio existente.
2. Usar una base PostgreSQL exclusiva de staging y las credenciales de prueba
   mediante variables protegidas del servicio. Mantener
   `POLYSCRIBE_ONE_ENABLED=0`. No compartir credenciales en chat ni en Git.
3. Confirmar respaldo y revisión actual del destino con:

   ```sh
   python -m flask --app 'app:create_app' db current --directory migrations
   python -m flask --app 'app:create_app' db heads --directory migrations
   ```

   El padre esperado de este cambio es `0e9c61264114`; la revisión nueva es
   `b7d2a8e41001`. Si el destino difiere, investigar antes de aplicar cambios.
   No usar el árbol antiguo `alembic/`.

4. Con el código nuevo disponible y conexiones de prueba cerradas, aplicar:

   ```sh
   python -m flask --app 'app:create_app' db upgrade --directory migrations b7d2a8e41001
   ```

   La migración crea dos tablas y sus índices; no modifica AudioJob ni convierte
   trabajos históricos. Revisar el resultado antes de activar la función.
5. Configurar `POLYSCRIBE_ONE_ENABLED=1` y reiniciar el servicio de staging.
6. Con una cuenta verificada de pruebas y minutos disponibles, subir una
   grabación corta no sensible con voz conocida. Usar el proveedor OpenAI ya
   configurado. Esta llamada real tiene el costo normal del proveedor y aún
   no se ha realizado desde este entorno.
7. Comprobar texto e idioma, resumen, historial y exportaciones; confirmar que
   el consumo corresponde a la duración de un único trabajo completado.
   Verificar una ejecución seleccionada para el job y segmentos ordenados
   con tiempos dentro de la grabación. Whisper no aporta diarización aquí;
   hablantes, confianza y costo quedan vacíos cuando no están disponibles.
8. Probar un error de proveedor controlado: job y ejecución deben quedar en
   error, sin resultado seleccionado ni consumo por ese trabajo. Confirmar
   `/healthz` y que los trabajos anteriores siguen accesibles.
9. Tras revisar esa evidencia, planificar la activación en producción con el
   mismo orden: código con función desactivada, migración, comprobación,
   activación y prueba controlada.

## Reversión

Desactivar `POLYSCRIBE_ONE_ENABLED` y reiniciar vuelve al camino anterior sin
eliminar las tablas ni sus datos. Este es el primer recurso ante un problema.
El downgrade elimina ejecuciones y segmentos: no ejecutarlo sobre datos que
deban conservarse sin un respaldo y un plan explícito. PostgreSQL necesita
bloqueos DDL; cerrar transacciones de prueba antes de ensayar una reversión.

## Límites actuales

El flujo sigue siendo síncrono. La selección entre proveedores, colas, interfaz
de evidencia y conservación del audio para reproducirlo quedan pendientes.
Las pruebas automáticas simulan OpenAI; no establecen precisión de transcripción
ni validan pagos reales. Esta entrega no resuelve por sí sola la baja activación
comercial: queda pendiente observar el recorrido de usuarios reales.
