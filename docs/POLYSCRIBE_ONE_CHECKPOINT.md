# PolyScribe One: checkpoint de desarrollo

Fecha: 2026-11-08. Rama local: `polyscribe-one-core`.

## Dirección acordada

PolyScribe One — AI Audio, Video & Knowledge OS. La propuesta
Conversation-to-Outcome OS convierte grabaciones en transcripciones, hablantes,
decisiones, tareas, evidencia, resúmenes, contenido, clips, traducciones,
workflows y conocimiento reutilizable.

El Best-Model Router seleccionará proveedores por idioma, ruido, hablantes,
calidad, costo, velocidad, confianza y contexto. El Evidence Engine vinculará
resultados con segmentos reproducibles de la fuente. Estas capacidades siguen
siendo objetivos; los modelos de este cambio son su infraestructura inicial.

## Implementado localmente

- `TranscriptionRun`: ejecuciones por proveedor y modelo, estado, errores,
  idioma, confianza, latencia, costo decimal, texto, metadatos y fechas.
- `TranscriptSegment`: segmentos por ejecución, secuencia, tiempos, hablante,
  texto, confianza y metadatos.
- Restricciones de integridad: secuencias únicas por ejecución, intervalos y
  métricas válidos, un máximo de una ejecución seleccionada por trabajo.
- Registro de ambos modelos en el paquete canónico `app.models`.
- Migración aditiva `b7d2a8e41001`, hija de `0e9c61264114`, bajo `migrations/`.
  El árbol antiguo `alembic/` permanece sin cambios.
- Adaptador `OpenAITranscriptionProvider` con texto, idioma, segmentos y latencia.
- Integración en `/jobs` mediante `POLYSCRIBE_ONE_ENABLED=1`, desactivada por
  defecto hasta que se aplique la migración. Guarda AudioJob, ejecución y
  segmentos en una misma transacción. Los fragmentos divididos usan tiempos
  globales; un error explícito de proveedor impide marcar el conjunto como completado.
  Un fragmento válido sin voz no invalida la voz de otros fragmentos.
- Veinticinco pruebas ejecutadas tanto en SQLite como en PostgreSQL 16 local.

Los campos de confianza son opcionales: no todos los proveedores los ofrecen
y sus valores no deben asumirse comparables sin calibración. No se inventan
hablantes, confianza ni costos. La integración sigue siendo síncrona; todavía
no hay selección automática entre proveedores ni Evidence Engine visible.

## Validación realizada

- Dependencias de `requirements.txt` instaladas en un entorno Linux aislado;
  `pip check` sin conflictos.
- Importación de los tres modelos y creación de la aplicación correctas.
- Veinticinco pruebas aprobadas en SQLite y las mismas veinticinco en PostgreSQL 16,
  incluidas persistencia desde `/jobs`, tiempos de fragmentos, errores parciales,
  compatibilidad con la función desactivada y respuesta de `/healthz`.
- Pruebas de flujo con WAV y ffprobe reales, sesión, usuario verificado,
  historial, cuota y aislamiento entre usuarios. Solo OpenAI está simulado en
  estos flujos; no se prueban envío de correo ni pagos externos.
- La preparación rechaza el conjunto si falla la generación de cualquier parte.
  Una prueba con FFmpeg real conserva incluso la cola final de 50 ms.
- Corregido el balance visible: solo cuenta AudioJobs con estado `done`, igual
  que la validación de minutos de `/jobs`. Antes contaba también errores.
- Compilación Python y `git diff --check` correctos.
- Migración aplicada, revertida y aplicada nuevamente en SQLite temporal,
  conservando un AudioJob previo. La base inicial se construyó desde los
  modelos existentes y se marcó como `0e9c61264114`; esto no valida la cadena
  histórica completa ni reproduce el esquema real de producción.
- Comparación del esquema resultante con los modelos sin diferencias.
- SQL de la nueva migración compilado y ejecutado en PostgreSQL 16 local.
  Aplicación, reversión y nueva aplicación correctas, sin diferencias entre
  esquema y modelos y conservando el AudioJob previo. La base inicial fue
  construida desde los modelos existentes; no es una copia de producción.

Pruebas reproducibles, con las dependencias instaladas:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
git diff --check
```

Las pruebas usan SQLite en memoria y una clave ficticia; no necesitan APIs
pagadas ni conexiones a producción. En este entorno el venv está fuera del
checkout porque el repositorio incluye archivos rastreados de un antiguo venv.
La variable opcional `POLYSCRIBE_TEST_DATABASE_URL` permite ejecutar la suite
contra una base desechable PostgreSQL. La suite crea y elimina tablas: usarla
exclusivamente con bases de pruebas.

## Pendiente

1. Confirmar la revisión y el esquema efectivos del destino antes de desplegar.
2. Revisar y publicar los cambios mediante el flujo de revisión del proyecto.
3. Aplicar la migración antes de activar `POLYSCRIBE_ONE_ENABLED=1`. Probar
   una grabación real con el proveedor en staging; las llamadas de esta suite
   están simuladas y no prueban la precisión de Whisper.
4. Avanzar hacia procesamiento en segundo plano, router y Evidence Engine.
5. Investigar el embudo comercial: el usuario reporta actualmente 174 usuarios
   sin transcripciones ni pagos. Es una cifra reportada, no verificada aquí;
   debe conciliarse con las cifras históricas del checkpoint anterior.

La entrega incluye un workflow de CI para SQLite/PostgreSQL y una prueba
automatizada de aplicación y reversión de la migración. El procedimiento de
staging y activación está en `docs/POLYSCRIBE_ONE_RELEASE.md`.
No se ha desplegado esta rama, accedido a producción ni contratado servicios
adicionales. El estado de publicación y revisión debe consultarse en GitHub.
